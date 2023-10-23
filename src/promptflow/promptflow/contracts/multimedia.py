import base64
import hashlib
import os
import uuid
from pathlib import Path
from typing import Callable


class PFBytes(bytes):
    """This class is used to represent a bytes object in PromptFlow.
    It has all the functionalities of a bytes object,
    and also has some additional methods to help with serialization and deserialization.
    """

    def __new__(cls, value: bytes, *args, **kwargs):
        # Here we must only pass the value to the bytes constructor,
        # otherwise we will get a type error that the constructor doesn't take such args.
        # See https://docs.python.org/3/reference/datamodel.html#object.__new__
        return super().__new__(cls, value)

    def __init__(self, data: bytes, mime_type: str):
        super().__init__()
        # Use this hash to identify this bytes.
        self._hash = hashlib.sha1(data).hexdigest()[:8]
        self._mime_type = mime_type

    @staticmethod
    def _get_extension_from_path(path: Path):
        return path.suffix[1:]

    @staticmethod
    def _get_extension_from_type(mime_type: str):
        ext = mime_type.split("/")[-1]
        return None if ext == "*" else ext

    def save_to_file(self, file_name: str, folder_path: Path, relative_path: Path = None):
        ext = PFBytes._get_extension_from_type(self._mime_type)
        file_name = f"{file_name}.{ext}" if ext else file_name
        image_info = {
            f"data:{self._mime_type}:path": str(relative_path / file_name) if relative_path else file_name
        }
        path = folder_path / relative_path if relative_path else folder_path
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, file_name), 'wb') as file:
            file.write(self)
        return image_info

    @classmethod
    def get_file_reference_encoder(cls, folder_path: Path, relative_path: Path = None) -> Callable:
        def pfbytes_file_reference_encoder(obj):
            """Dumps PFBytes to a file and returns its reference."""
            if isinstance(obj, PFBytes):
                file_name = str(uuid.uuid4())
                return obj.save_to_file(file_name, folder_path, relative_path)
            raise TypeError(
                f"Object of type '{type(obj).__name__}' is not JSON serializable"
            )

        return pfbytes_file_reference_encoder


class Image(PFBytes):
    def __init__(self, data: bytes, mime_type: str = "image/*"):
        return super().__init__(data, mime_type)

    @staticmethod
    def from_file(f: Path):
        ext = PFBytes._get_extension_from_path(f)
        mime_type = f"image/{ext}" if ext else "image/*"
        with open(f, "rb") as fin:
            return Image(fin.read(), mime_type=mime_type)

    def __str__(self):
        return f"Image({self._hash})"

    def to_base64(self):
        return base64.b64encode(self).decode("utf-8")

    def serialize(self, encoder: Callable = None):
        return self.__str__() if encoder is None else encoder(self)
