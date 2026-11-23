"""Mock edX classes"""
from unittest.mock import Mock


class CourseEnrollmentException(Exception):
    pass


class NonExistentCourseError(CourseEnrollmentException):
    pass


class EnrollmentClosedError(CourseEnrollmentException):
    pass


class CourseFullError(CourseEnrollmentException):
    pass


class AlreadyEnrolledError(CourseEnrollmentException):
    pass


class InvalidKeyError(Exception):
    pass


class SvgPathImage:
    pass


class QRCode:
    def __init__(self, image_factory=None):
        """Initialize the recorded QR-code options and generation state."""
        self.image_factory = image_factory
        self.data_added = None
        self.made = False

    def to_string(self, encoding='unicode'):
        """Return a deterministic SVG representation for invoice rendering."""
        return '<svg>fake qr code</svg>'

    def add_data(self, data):
        """Record the data supplied by the invoice renderer."""
        self.data_added = data

    def make(self, fit=True):
        """Record that QR generation was requested with the given fit option."""
        self.made = fit

    def make_image(self):
        """Return an image double exposing the SVG serialization interface."""
        mock_image = Mock()
        mock_image.to_string.return_value = '<svg>fake qr code</svg>'
        return mock_image
