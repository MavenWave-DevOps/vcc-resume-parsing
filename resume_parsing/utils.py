import logging
import pathlib
import re
from itertools import islice
from typing import List
from xml.sax.saxutils import escape

import numpy as np
import numpy.ma as ma

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def split_gcs_uri(document_path: str):
    """Split a GCS URI into its components.

    gs://[bucket]/[path/to/folder]/[filename].[extension]

    Args:
        document_path (str): The GCS URI

    Returns:
        Tuple[str]: bucket, path, filename, extension
    """
    return re.match(
        r"gs:\/\/([^\/]+)\/(?:(.*)\/)?([^\/]+)\.([^\.]*)$", document_path
    ).groups()


def chunked(generator, size):
    """Read parts of the generator, pause each time after a chunk.

    https://stackoverflow.com/questions/8290397/how-to-split-an-iterable-in-constant-size-chunks
    """
    gen = iter(generator)
    return iter(lambda: list(islice(gen, size)), [])


def batch_pages(num_pages, batch_size=5):
    """Yield page batches for synchronous calls to Vision API."""
    pages = range(1, num_pages + 1)
    page_batches = chunked(pages, batch_size)
    for batch in page_batches:
        yield batch


class GCSPath(pathlib.PurePosixPath):
    """Pathlib-style wrapper for GCS URIs."""

    def __new__(cls, gcs_path: str):
        if gcs_path.startswith("gs://"):
            gcs_path = gcs_path[5:]
        return super().__new__(cls, gcs_path)

    def __str__(self):
        return "gs://" + super().__str__()


def to_xml(results) -> str:
    """Convert the dictionary to an XML string."""
    _internal = ""
    if isinstance(results, dict):
        for key, value in results.items():
            if key == "ResumeData":
                _internal += '<?xml version="1.0" standalone="yes"?>\n'
                _internal += f'<{key}  xmlns="http://tempuri.org/ResumeData.xsd">'
                _internal += to_xml(value)
                _internal += f"</{key}>"
            elif isinstance(value, list):
                for elem in value:
                    _internal += f"<{key}>"
                    _internal += to_xml(elem)
                    _internal += f"</{key}>"
            else:
                if isinstance(value, dict):
                    if len(value.items()) == 0:
                        continue

                _internal += f"<{key}>"
                _internal += to_xml(value)
                _internal += f"</{key}>"
    else:
        _internal += escape(str(results))
    return _internal


def align(a: List[int], b: List[int]):
    """Align two lists of possibly unequal length.

    Attempts merge and alignment of two lists containing position indexes by
    finding the positions that closest to one another.

    Example:
        >> a = [1, 2, 5, 8, 10, 22]
        >> b = [1, 2, 3, 4, 6, 9, 12, 13, 17, 20]
        >> list(align(a, b))
        [(0, 0),
        (1, 1),
        (None, 2),
        (2, 3),
        (None, 4),
        (3, 5),
        (4, 6),
        (None, 7),
        (None, 8),
        (5, 9)]

    Args:
        a (List[int]): The first list of indexes
        b (List[int]): The second list of indexes

    Returns:
        generator[Tuple[int]]: A generator of tuple-pairs of index positions
        from a and b
    """
    i = 0
    j = 0
    # Matrix of pair-wise differences to find which next two indexes are the
    # closest to each other
    compare = np.abs(np.array(a)[:, None] - np.array(b)[None, :])
    while i < len(a) or j < len(b):
        try:
            # Mask positions not being compared
            mask = np.zeros(compare.shape)
            mask[i + 1 :, j + 1 :] = 1  # Future comparisons
            mask[:i, :] = 1  # Already yielded
            mask[:, :j] = 1  # Already yielded
            masked_compare = ma.array(compare, mask=mask)

            # Tuple indicating position in matrix which is the minimum
            minc = np.unravel_index(masked_compare.argmin(), compare.shape)

            if minc[0] < i or minc[1] < j:
                raise ValueError

            # If the min-tuple is not the top-left corner (0, 0)
            # then some values in either a or b are not matched
            # Yield each of these:
            for ii in range(i, minc[0]):
                yield (ii, None)
            for jj in range(j, minc[1]):
                yield (None, jj)

            # Yield the next pair
            yield (minc[0], minc[1])

            i = minc[0] + 1
            j = minc[1] + 1
        except ValueError:
            for ii in range(i, len(a)):
                yield (ii, None)
            for jj in range(j, len(b)):
                yield (None, jj)
            break
