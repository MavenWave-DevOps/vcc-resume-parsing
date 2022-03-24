from inspect import GEN_CREATED
import re
from typing import List, Optional
from string import punctuation
from wsgiref.simple_server import demo_app

# from scipy.fftpack import sc_diff

from rapidfuzz import fuzz

from resume_parsing.utils import align

# from utils import align

strip_chars = punctuation.replace(".", "") + " \n\t\s"


def parse(ner_inference: dict, resume: str):
    """Executes rule-based parsing on a document.

    Args:
        ner_inference (dict): The NER prediction response.
        resume (str): Resume text.

    Returns:
        dict: A dictionary with the parsed resume.
    """
    job_history = []
    identification_fields = []

    first_names = extract_entity_text(ner_inference, resume, entity="FST_NAM")
    last_names = extract_entity_text(ner_inference, resume, entity="LAST_NAM")
    emails = extract_entity_text(ner_inference, resume, entity="EMAIL_ADR")
    company_indices = extract_entity_text(
        resume=resume, ner_inference=ner_inference, entity="ER_NAM", return_indices=True
    )

    position_indices = extract_entity_text(
        resume=resume,
        ner_inference=ner_inference,
        entity="POSN_NAM",
        return_indices=True,
    )

    descriptions = get_description(ner_inference, resume)
    dates = get_dates(ner_inference, resume, position_indices)
    phone = get_phone_numbers(ner_inference, resume)
    address = get_addresses(resume)
    cert = get_certificates(resume)

    edu_history, degrees = align_education(ner_inference, resume)
    educ_level_cd = [standardize_degree(d) for d in degrees]
    fname = first_names[0].strip(strip_chars) if first_names else None
    lname = last_names[0].strip(strip_chars) if last_names else None
    email = validate_emails(emails)
    zip_cd = address[0][0] if address else None
    st_addr = address[0][1].strip(strip_chars) if address else None

    if fname:
        identification_fields.append({"FST_NAM": fname})

    if lname:
        identification_fields.append({"LAST_NAM": lname})

    if email:
        identification_fields.append(
            {"EMAIL_ADR": email.encode("ascii", "ignore").decode()}
        )

    if zip_cd:
        identification_fields.append({"ZIP_CD": zip_cd})

    if st_addr:
        identification_fields.append(
            {"L1_ADR": st_addr.encode("ascii", "ignore").decode()}
        )

    if cert:
        identification_fields.append(
            {"AWRD_CERT_TXT": ",".join(cert).encode("ascii", "ignore").decode()}
        )

    if educ_level_cd:
        highest_degree = (
            "08" if max(educ_level_cd) == 0 else "0" + str(max(educ_level_cd))
        )
        identification_fields.append({"EDUC_LVL_CD": highest_degree})

    if phone:
        for p in phone:
            area_cd, pnum = p
            identification_fields.append({"PHN_AREA_CD": area_cd})
            identification_fields.append({"PHN_NUM": pnum})

    if dates or descriptions or company_indices or position_indices:
        job_history = get_job_history(dates, descriptions)

    return {
        "ResumeData": {
            "CUST_RSUM": {k: v for i in identification_fields for k, v in i.items()},
            "RSUM_EDUC_HIST": edu_history,
            "RSUM_WORK_HIST": job_history,
        }
    }


def get_phone_numbers(ner_inference: dict, resume: str):
    """Extracts phone numbers.

    Args:
        ner_inference (dict): The NER prediction response.
        resume (str): Resume text.

    Returns:
        [tuple]: List containing the area code and the 7 digit number.
    """

    phone_numbers = extract_entity_text(
        resume=resume,
        ner_inference=ner_inference,
        entity="PHONE_NUMBER",
    )

    if not phone_numbers:
        return []

    phone_numbers = [
        re.search(r"\(?(\d{3})\)?[^\w]??(\d{3}[^\w]?\d{4})", p) for p in phone_numbers
    ]

    return [
        (match.groups()[0], re.sub(r"[^0-9]", "", match.groups()[1]))
        for match in phone_numbers
        if match
    ]


def get_addresses(resume: str):
    """Extracts addresses.

    Args:
        resume (str): The resume text.

    Returns:
        [tuple]: Nested list containing the street address and zip code.
    """
    street_address_pattern = re.compile(
        r"\d{1,4} [\w\s]{1,20}(?:street|st|avenue|ave|road|rd|highway|"
        r"hwy|square|sq|trail|trl|drive|dr|court|ct|park|parkway|pkwy|"
        r"circle|cir|boulevard|blvd)\W?(?=\s|$)",
        re.IGNORECASE,
    )
    zip_pattern = re.compile(r"\b\d{5}(?:[-\s]\d{4})?\b")
    heading = [
        "reference",
        "education",
        "volunteer",
        "skill",
        "certification",
        "military",
        "affiliat",
    ]

    reduc_text = resume
    for h in heading:
        reduc_text = reduc_text.split(h)[0]

    address = re.findall(street_address_pattern, reduc_text)
    address = [re.sub(r"\W+", " ", i) for i in list(address)]
    address = [" ".join(i.split()) for i in address]

    zip_code = re.findall(zip_pattern, reduc_text)

    return [(a, z) for a, z in zip(zip_code, address)]


def get_degrees(ner_inference: dict, resume: str):
    """Extracts academic degrees.

    Args:
        ner_inference (dict): The NER prediction response.
        resume (str): Resume text.

    Returns:
        [str]: List containing the degrees.
    """
    degrees = extract_entity_text(
        resume=resume, ner_inference=ner_inference, entity="EDUC_DET_TXT"
    )
    degrees = [re.findall(r"[a-zA-Z\.]+", i) for i in list(degrees)]
    degrees = [" ".join(i) for i in degrees]

    return degrees


def get_certificates(resume: str):
    """Extracts educational certificates.

    Args:
        resume (str): The resume text.

    Returns:
        [str]: List containing the certifications.
    """
    certs = []
    lines = resume.split("\n")
    for line in lines:
        if "cert" in line.lower():
            match = re.findall(r"\b[A-Z].*?Cert[a-z]*\b", line)
            if match:
                for m in match:
                    certs.append(m)
    return certs


def get_description(ner_inference: dict, resume: str):
    """Extracts job descriptions related to job positions.

    Args:
        ner_inference (dict): The NER prediction response.
        resume (str): Resume text.

    Returns:
        [dict]: List of job descriptions keyed by job positions.
    """
    work_history = []
    position_indices = extract_entity_text(
        resume=resume,
        ner_inference=ner_inference,
        entity="POSN_NAM",
        return_indices=True,
    )

    company_indices = extract_entity_text(
        resume=resume,
        ner_inference=ner_inference,
        entity="ER_NAM",
        return_indices=True,
    )

    if not company_indices and not position_indices:
        return []

    aligned = align([i[0] for i in company_indices], [i[0] for i in position_indices])
    left_align, right_align = zip(*aligned)
    company_indices = (
        [company_indices[i] if i is not None else None for i in left_align]
        if company_indices
        else [None for i in left_align]
    )
    position_indices = (
        [position_indices[i] if i is not None else None for i in right_align]
        if position_indices
        else [None for i in right_align]
    )
    companies = [resume[i[0] : i[1]] if i else None for i in company_indices]
    positions = [resume[i[0] : i[1]].strip() if i else None for i in position_indices]

    for i, (ci, pi, c, p) in enumerate(
        zip(company_indices, position_indices, companies, positions)
    ):
        comp_start = ci[1] if ci else ci
        pos_start = pi[1] if pi else pi

        start = (
            max(comp_start, pos_start)
            if comp_start and pos_start
            else comp_start or pos_start
        )  # + 1

        if len(left_align) == i + 1:  # identify last job provided
            section_pattern = re.compile(
                r"(reference|education|volunteer|skill|certificat|military|award"
                r"|interest|additional|professional development|assessment|\n\n\n)",
                re.IGNORECASE,
            )
            description = re.split(section_pattern, resume[start:])[0]

        else:  # index based on next job's start position
            comp_end = (
                company_indices[i + 1][0]
                if company_indices[i + 1]
                else company_indices[i + 1]
            )
            pos_end = (
                position_indices[i + 1][0]
                if position_indices[i + 1]
                else position_indices[i + 1]
            )

            end = (
                min(comp_end, pos_end) if comp_end and pos_end else comp_end or pos_end
            )

            description = resume[start:end].split("\n\n\n")[0]

        work_history.append(
            {
                "description": {p: description.strip()},
                "company": {p: c},
                "right_aligned": right_align,
                "left_aligned": left_align,
                "company_indices": company_indices,
                "position_indices": position_indices,
            },
        )

    return work_history


def extract_entity_text(
    ner_inference: dict, resume: str, entity: str, return_indices: bool = False
):
    """Extract an entity from the NER prediction.

    Args:
        ner_inference (dict): The NER prediction response.
        resume (str): Resume text.
        entity (str): The entity/field.
        return_indices (bool, optional): True to return entity indices.
            Defaults to False.

    Returns:
        [type]: List containing index positions when return_indices=True.
                Else, return list of entities.
    """
    if entity not in ner_inference["displayNames"]:
        entity_indices = []
    else:
        entity_indices = [
            idx
            for idx, elem in enumerate(ner_inference["displayNames"])
            if elem == entity
        ]
    if not entity_indices:
        entity_values = []
    else:
        unordered_dict = {
            idx: int(v)
            for idx, v in enumerate(ner_inference["textSegmentStartOffsets"])
            if idx in entity_indices
        }
        ordered_dict = {
            k: v for k, v in sorted(unordered_dict.items(), key=lambda item: item[1])
        }
        order_keys = list(ordered_dict.keys())

        entity_values = [
            (
                int(ner_inference["textSegmentStartOffsets"][idx]),
                int(ner_inference["textSegmentEndOffsets"][idx]) + 1,
            )
            for idx in order_keys
        ]
    if not return_indices:
        entity_values = [resume[i[0] : i[1]] for i in entity_values]
    return entity_values


def get_dates(ner_inference: dict, resume: str, position_indices):
    """Extracts dates related with job positions.

    Args:
        ner_inference (dict): The NER prediction response.
        resume (str): Resume text.
        position_indices ([tuple]): The start and end index of job positions.

    Returns:
        [dict]: List of dates.
    """
    dates = []
    positions = []
    if not position_indices:
        return []

    written_months = (
        r"jan(?:\.|uary)?|feb(?:\.|ruary)?|mar(?:\.|ch)?|apr(?:\.|il)?|may"
        r"|jun(?:\.|e)?|jul(?:\.|y)?|aug(?:\.|ust)?|sept(?:\.|ember)?|oct"
        r"(?:\.|ober)?|nov(?:\.|ember)?|dec(?:\.|ember)"
    )
    split_pattern = r"[^\w]?(?:-|–|to|thru|through)?[^\w]?"
    date_pattern = (
        r"(?:\d{1,2}\/\d{1,2}\/\d{2,4})|"  # mm/dd/yy | mm/dd/yyyy
        r"(?:(?<![\d\/])(?:1[0-2]|0?[1-9])\/\d{2,4}(?<!\/))|"  # mm/yyyy | mm/yy
        fr"(?:(?:{written_months})?(?:[^\w]+\d{{1,2}},)?[^\w\/]*(?:19|20)\d{{2}})|"  # noqa: E501 mmm d, yyyy | yyyy
        r"(?:current|present)"
    )
    combined_pattern = f"({date_pattern})(?:{split_pattern}({date_pattern}))?"
    pattern1 = re.compile(combined_pattern, re.IGNORECASE)

    for pos in position_indices:
        s, e = pos
        positions.append(resume[int(s) : int(e)].strip())

        start_lines = [m.start() for m in re.finditer(r"\n", resume[: int(s)])]
        start_window = (
            start_lines[-3]
            if len(start_lines) > 2
            else s - 100  # Search up to 3 line breaks above
        )
        end_lines = [m.start() for m in re.finditer(r"\n", resume[int(e) :])]
        end_window = (
            e + end_lines[1]
            if len(end_lines) > 2
            else e + 100  # Search up to 2 line breaks below
        )
        windowed_text = " ".join(resume[start_window:end_window].split())
        experience = re.findall(pattern1, windowed_text)
        if len(experience) > 0:
            dates.append(experience)
        else:
            dates.append(None)

    dates = process_dates(dates)
    result = [{k: v} for k, v in zip(positions, dates)]

    return result


def standardize_degree(degree: str):
    """Standardize degrees based on education level.

    Args:
        degree (str): The degree.

    Returns:
        int: The degree level.
    """
    education_level = {
        "Other": 0,
        "HighSchool": 1,
        "Cert": 2,
        "Associate": 3,
        "Bachelor": 5,
        "Masters": 6,
        "PHD": 7,
    }

    if "bachelor" in degree.lower():
        result = "Bachelor"
    elif "b.s." in degree.lower():
        result = "Bachelor"

    elif "BS" in degree:
        result = "Bachelor"

    elif "b.a." in degree.lower():
        result = "Bachelor"

    elif "associate degree" in degree.lower():
        result = "Associate"

    elif "associates" in degree.lower():
        result = "Associate"

    elif "associate" in degree.lower():  # dangerous
        result = "Associate"

    elif "master of" in degree.lower():
        result = "Masters"
    elif "masters" in degree.lower():
        result = "Masters"

    elif "MBA" in degree:  # dangerous
        result = "Masters"

    elif "master" in degree.lower():  # dangerous
        result = "Masters"

    elif "m.s." in degree.lower():
        result = "Masters"

    elif "MS" in degree:
        result = "Masters"

    elif "doctora" in degree.lower():
        result = "PHD"

    elif "ph.d" in degree.lower():
        result = "PHD"

    elif "phd" in degree.lower():
        result = "PHD"

    elif "certificat" in degree.lower():
        result = "Cert"
    elif any(fuzz.ratio(i.lower(), "bachelor") > 90 for i in degree.split()):
        result = "Bachelor"
    elif "BA" in degree:  # dangerous!!!
        result = "Bachelor"
    elif any(fuzz.ratio(i.lower(), "masters") > 85 for i in degree.split()):
        result = "Masters"
    elif any(fuzz.ratio(i.lower(), "associate") > 90 for i in degree.split()):
        result = "Associate"
    elif any(fuzz.ratio(i.lower(), "certificate") > 60 for i in degree.split()):
        result = "Cert"
    elif "high school" in degree.lower():
        result = "HighSchool"
    elif "HS" in degree:
        result = "HighSchool"
    elif "ged" in "".join(degree.lower().split(".")):
        result = "HighSchool"
    elif "hsed" in "".join(degree.lower().split(".")):
        result = "HighSchool"
    else:
        result = "Other"

    return education_level[result]


def process_dates(dates: list):
    """Post-processing of extracted dates.

    Args:
        dates (list): List of dates.

    Returns:
        [dict]: List of dates.
    """
    processed_dates = []
    calendar_months = {
        "jan": "1",
        "feb": "2",
        "mar": "3",
        "apr": "4",
        "may": "5",
        "jun": "6",
        "jul": "7",
        "aug": "8",
        "sep": "9",
        "oct": "10",
        "nov": "11",
        "dec": "12",
    }
    for d in dates:
        # from re.findall
        if isinstance(d, list):
            if isinstance(d[0], str):
                d = " ".join(d).strip()
            elif isinstance(d[0], tuple):
                d = " ".join([" ".join(list(x)) for x in d]).strip()

        start_month, start_year = None, None
        end_month, end_year = None, None

        if d:
            if len(re.sub(r"[^0-9A-Za-z]", "", d)) == 8:
                start_year = d[:4]
                end_year = d[-4:]
            elif len(d) == 4:
                start_year = d
                end_year = d

            elif any([x in d.lower() for x in ["present", "current"]]):
                end_year = "Present"
                if "/" in d:
                    parts = re.sub(r"[^0-9/]", "", d).split("/")
                    if len(parts) == 2:
                        start_year = parts[1]
                        start_month = parts[0]
                    elif len(parts) == 3:
                        start_year = parts[2]
                        start_month = parts[0]
                else:
                    if d[:4].isnumeric():
                        start_year = d[:4]
                    else:
                        if d[-3:].isnumeric():
                            start_year = d[-4:]
                            start_month = re.sub(r"[^A-Za-z]", "", d)
            else:

                if "/" in d:
                    d = re.sub(r"[^0-9/]", " ", d)
                    if " " in d:
                        start_date = d.split()[0]
                        end_date = d.split()[1]
                    else:
                        start_date = d
                        end_date = ""

                    start_parts = start_date.split("/")
                    end_parts = end_date.split("/")

                    if len(start_parts) == 2:
                        start_year = start_parts[1]
                        start_month = start_parts[0]

                    if len(start_parts) == 3:
                        start_year = start_parts[2]
                        start_month = start_parts[0]

                    if len(end_parts) == 2:
                        end_year = end_parts[1]
                        end_month = end_parts[0]

                    if len(end_parts) == 3:
                        end_year = end_parts[2]
                        end_month = end_parts[0]

                else:
                    d = re.sub(r"[^0-9A-Za-z]", " ", d)
                    d = " ".join(d.split()).split()
                    end_year = d[-1]
                    end_month = d[-2]
                    start_year = d[1]
                    start_month = d[0]

            if start_month:
                for c in calendar_months:
                    if c in start_month.lower():
                        start_month = calendar_months[c]
                        break

            if end_month:
                for c in calendar_months:
                    if c in end_month.lower():
                        end_month = calendar_months[c]
                        break

        processed_dates.append(
            {"start": (start_month, start_year), "end": (end_month, end_year)}
        )
    return processed_dates


def align_education(ner_inference: dict, resume: str):
    """Pairs instituitions with the respective education description.

    Args:
        ner_inference (dict): The NER prediction response.
        resume (str): Resume text.

    Returns:
        edu_history [dict]: List of education history.
        degrees [str]: List of education description.
    """
    edu_history = []

    institutions_indices = extract_entity_text(
        resume=resume,
        ner_inference=ner_inference,
        entity="INST_NAM",
        return_indices=True,
    )
    degrees_indices = extract_entity_text(
        resume=resume,
        ner_inference=ner_inference,
        entity="EDUC_DET_TXT",
        return_indices=True,
    )

    institutions = [
        resume[i[0] : i[1]].strip(strip_chars) for i in institutions_indices
    ]
    degrees = [resume[i[0] : i[1]].strip(strip_chars) for i in degrees_indices]
    aligned = align(
        [i[0] for i in institutions_indices], [i[0] for i in degrees_indices]
    )

    for pair in aligned:
        if pair[1] is None:
            edu_history.append({"INST_NAM": institutions[pair[0]]})
        elif pair[0] is None:
            edu_history.append({"EDUC_DET_TXT": degrees[pair[1]]})
        else:
            edu_history.append(
                {"INST_NAM": institutions[pair[0]], "EDUC_DET_TXT": degrees[pair[1]]}
            )

    return edu_history, degrees


def get_job_history(
    dates: List[dict],
    work_history: List[dict],
):
    """Post-processing for work related fields

    Args:
        dates ([dict]): The parsed dates. See get_dates function.
        work_history ([dict]): Parsed results from get_description.
            Contains aligned companies, job descriptions, and positions

    Returns:
        [dict]: List of job descriptions.
    """
    job_history = []
    if (
        work_history[0]["company_indices"] == []
        and work_history[0]["position_indices"] == []
    ):
        if dates == []:
            return job_history

    dates = (
        [dates[i] if i is not None else None for i in work_history[0]["right_aligned"]]
        if dates
        else [None for i in work_history[0]["right_aligned"]]
    )

    for dt, wh in zip(dates, work_history):
        job_record = {}
        pos = list(wh["company"].keys())[0]

        start_month = None if dt is None else dt[pos]["start"][0]
        start_year = None if dt is None else dt[pos]["start"][1]
        end_month = None if dt is None else dt[pos]["end"][0]
        end_year = None if dt is None else dt[pos]["end"][1]
        job_descr = wh["description"][pos]
        comp = wh["company"][pos]

        # remove overlapping jobs
        if job_descr:
            lines = job_descr.split("\n")
            state_counts = 0  # state should only appear once per job
            processed_job_descr = []
            for idx, l in enumerate(lines):
                if idx == 0 and len(l) < 20:
                    continue

                state_pattern = re.compile(
                    r",\s*(?:AL|Alabama|AK|Alaska|AZ|Arizona|AR|Arkansas"
                    r"|CA|California|CO|Colorado|CT|Connecticut|DE|Delaware|FL|Florida|GA|Georgia"
                    r"|HI|Hawaii|ID|Idaho|IL|Illinois|IN|Indiana|IA|Iowa|KS|Kansas"
                    r"|KY|Kentucky|LA|Louisiana|ME|Maine|MD|Maryland|MA|Massachusetts|MI|Michigan"
                    r"|MN|Minnesota|MS|Mississippi|MO|Missouri|MT|Montana|NE|Nebraska|NV|Nevada"
                    r"|NH|New Hampshire|NJ|New Jersey|NM|New Mexico|NY|New York|NC|North Carolina"
                    r"|ND|North Dakota|OH|Ohio|OK|Oklahoma|OR|Oregon|PA|Pennsylvania|RI|Rhode Island"
                    r"|SC|South Carolina|SD|South Dakota|TN|Tennessee|TX|Texas|UT|Utah|VT|Vermont"
                    r"|VA|Virginia|WA|Washington|WV|West Virginia|WI|Wisconsin|WY|Wyoming)"
                )

                state_match = re.search(state_pattern, l)
                if state_match:
                    state_counts += 1
                    if state_counts == 2:
                        break
                else:
                    processed_job_descr.append(l)

        if comp:
            job_record["ER_NAM"] = comp.strip(strip_chars)
        if pos:
            job_record["POSN_NAM"] = (
                pos.encode("ascii", "ignore")
                .decode()
                .strip(punctuation + " " + " \n\s\t")
            )
        if start_month:
            job_record["STRT_MO"] = start_month
        if start_year:
            job_record["STRT_YR"] = start_year
        if end_month:
            job_record["END_MO"] = end_month
        if end_year:
            job_record["END_YR"] = end_year
        if job_descr:
            job_record["RESP_TXT"] = (
                "\n".join(processed_job_descr)
                .encode("ascii", "ignore")
                .decode()
                .strip(strip_chars)
            )

        job_history.append(job_record)

    return job_history


def validate_emails(emails: List[str]) -> Optional[str]:
    """Find best match for emails

    Args:
        emails [str]: Emails sorted by start position.

    Returns:
        str: The email.
    """
    email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    match = None
    for e in emails:
        match = re.search(email_pattern, e)
        if match:
            match = match[0]
            break

    return match
