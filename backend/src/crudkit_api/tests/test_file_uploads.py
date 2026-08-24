import base64
import io
import zipfile

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import ValidationError

from crudkit_api.serializers import CustomBase64FileField


def data_url(mime_type, content):
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


class CustomBase64FileFieldTests(SimpleTestCase):
    def setUp(self):
        self.field = CustomBase64FileField()

    def test_detects_content_instead_of_trusting_mime_type(self):
        uploaded = self.field.to_internal_value(data_url("application/octet-stream", b"%PDF-1.7\n"))
        self.assertTrue(uploaded.name.endswith(".pdf"))

    def test_rejects_unsupported_content_with_allowed_mime_type(self):
        with self.assertRaises(ValidationError):
            self.field.to_internal_value(data_url("application/pdf", b"MZ executable"))

    def test_rejects_invalid_base64_with_validation_error(self):
        with self.assertRaises(ValidationError):
            self.field.to_internal_value("data:application/pdf;base64,!!!")

    @override_settings(CRUDKIT_MAX_BASE64_FILE_SIZE=4)
    def test_rejects_oversized_content(self):
        with self.assertRaises(ValidationError):
            self.field.to_internal_value(data_url("text/plain", b"12345"))

    def test_detects_ooxml_container(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", "<document />")

        uploaded = self.field.to_internal_value(
            data_url("application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer.getvalue())
        )

        self.assertTrue(uploaded.name.endswith(".docx"))
