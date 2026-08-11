import datetime
import logging
import time

import jwt
from django.conf import settings
from django.utils import timezone


class Widget:
    def __init__(self, width=1):
        self.width = width

    def data(self):
        """
        Returns the data for the widget.
        This method should be overridden by subclasses to provide specific data.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def get_title(self):
        """
        Returns the title for the widget.
        Default is the class name, but subclasses can override this.
        """
        return self.__class__.__name__

    def json(self):
        return {
            "type": self.__class__.__mro__[1].__name__,  # TODO: Work with sub sub classes
            "title": self.get_title(),
            "data": self.data(),
            "width": self.width,
        }


class MetabaseEmbeddedQuestionWidget(Widget):
    question_id = None

    def data(self):
        secret_key = getattr(settings, "METABASE_SECRET_KEY", None)
        site_url = getattr(settings, "METABASE_SITE_URL", None)
        if not secret_key or not site_url:
            return {
                "error": "METABASE_SECRET_KEY / METABASE_SITE_URL not set in settings.",
            }
        payload = {
            "resource": {"question": self.question_id},
            "params": {},
            "exp": round(time.time()) + (60 * 10),  # 10 minute expiration
        }
        token = jwt.encode(payload, secret_key, algorithm="HS256")

        return {
            "url": site_url + "/embed/question/" + token + "#bordered=false&titled=false",
        }


class ChartWidget(Widget):
    """
    Widget for displaying charts using Chart.js.

    Subclasses should implement get_chart_data() to return the data
    needed for their specific chart.
    """

    chart_type = "line"  # 'line' or 'bar'

    # Standard color palette for consistent chart styling
    CHART_COLORS = [
        {"bg": "rgba(54, 162, 235, 0.6)", "border": "rgba(54, 162, 235, 1)"},  # Blue
        {"bg": "rgba(255, 99, 132, 0.6)", "border": "rgba(255, 99, 132, 1)"},  # Red
        {"bg": "rgba(255, 206, 86, 0.6)", "border": "rgba(255, 206, 86, 1)"},  # Yellow
        {"bg": "rgba(75, 192, 192, 0.6)", "border": "rgba(75, 192, 192, 1)"},  # Green
        {"bg": "rgba(153, 102, 255, 0.6)", "border": "rgba(153, 102, 255, 1)"},  # Purple
        {"bg": "rgba(255, 159, 64, 0.6)", "border": "rgba(255, 159, 64, 1)"},  # Orange
        {"bg": "rgba(201, 203, 207, 0.6)", "border": "rgba(201, 203, 207, 1)"},  # Grey
        {"bg": "rgba(75, 150, 110, 0.6)", "border": "rgba(75, 150, 110, 1)"},  # Dark Green
    ]

    def get_chart_data(self):
        """
        Returns the chart data for Chart.js.

        Should return a dictionary with:
        - labels: list of labels for the x-axis
        - datasets: list of datasets, each with label, data, backgroundColor, etc.

        Note: This method is now deprecated. Implement _get_chart_data instead.
        """
        return self._get_chart_data()

    def _get_chart_data(self):
        """
        Protected method for actual chart data generation.
        Subclasses should override this method instead of get_chart_data.
        """
        raise NotImplementedError("Subclasses must implement _get_chart_data method.")

    def get_chart_options(self):
        """
        Returns custom chart options for Chart.js.

        Override this method to provide chart-specific options.
        """
        return {}

    def get_chart_urls(self):
        """
        Returns URLs for chart data points (for clickable features).
        Override this method to provide URLs for data points.
        Should return a list of dictionaries, where each dictionary maps
        data indices to URLs for a specific dataset.
        """
        return None

    def generate_week_labels(self, num_weeks=4):
        """
        Utility method to generate week labels for time-series charts.
        Returns a tuple of (week_labels, week_boundaries).
        week_labels is a list of formatted week strings, e.g. "Jun 01-07"
        week_boundaries is a list of (start_date, end_date) tuples for each week
        """
        end_date = timezone.now()
        weeks = []
        week_labels = []

        for i in range(num_weeks):
            week_end = end_date - datetime.timedelta(weeks=i)
            week_start = week_end - datetime.timedelta(weeks=1)
            weeks.insert(0, (week_start, week_end))
            week_label = f"{week_start.strftime('%b %d')}-{week_end.strftime('%d')}"
            week_labels.insert(0, week_label)

        return week_labels, weeks

    def create_standard_axes_options(self, x_title="", y_title="", y_begin_at_zero=True, y_min=None, y_max=None):
        """
        Utility method to create standard axis options with consistent styling.
        """
        options = {
            "scales": {
                "x": {
                    "title": {"display": bool(x_title), "text": x_title, "color": "#333"},
                    "grid": {"display": True, "color": "rgba(200, 200, 200, 0.3)"},
                    "ticks": {"color": "#666"},
                },
                "y": {
                    "title": {"display": bool(y_title), "text": y_title, "color": "#333"},
                    "grid": {"display": True, "color": "rgba(200, 200, 200, 0.3)"},
                    "ticks": {"color": "#666"},
                },
            },
            "plugins": {
                "legend": {
                    "position": "top",
                    "labels": {
                        "boxWidth": 10,
                        "padding": 10,
                        "color": "#333",
                    },
                },
                "tooltip": {"mode": "index", "intersect": False},
            },
            "maintainAspectRatio": False,
        }

        if y_begin_at_zero:
            options["scales"]["y"]["beginAtZero"] = True

        if y_min is not None:
            options["scales"]["y"]["min"] = y_min

        if y_max is not None:
            options["scales"]["y"]["max"] = y_max

        return options

    def data(self):
        try:
            result = {
                "type": self.chart_type,
                "chartData": self._get_chart_data(),
                "options": self.get_chart_options(),
            }

            urls = self.get_chart_urls()
            if urls:
                result["urls"] = urls

            return result
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error in {self.__class__.__name__}: {str(e)}")

            # Return a chart with error information
            return {
                "type": "bar",  # Simple bar chart for error display
                "chartData": {
                    "labels": ["Error"],
                    "datasets": [
                        {
                            "label": f"Error: {str(e)}",
                            "data": [0],
                            "backgroundColor": "rgba(255, 99, 132, 0.6)",
                            "borderColor": "rgba(255, 99, 132, 1)",
                            "borderWidth": 1,
                        }
                    ],
                },
                "options": {
                    "scales": {"y": {"beginAtZero": True}},
                    "plugins": {"legend": {"display": True, "position": "top"}},
                },
            }


class ListWidget(Widget):
    """
    Widget for displaying a list of objects from the database.

    This widget allows filtering and limiting the number of results.
    """

    obj = None
    limit = 5  # Default limit of items to display

    def get_filters(self):
        """
        Returns the filters to apply to the queryset.

        Format: List of [field_name, operator, value] lists
        Example: [["status", "=", "active"], ["created_at", ">", "2023-01-01"]]

        Operators: =, !=, >, <, >=, <=, in, contains, startswith, endswith
        """
        return []

    def get_display_fields(self):
        """
        Returns the fields to display in the list.

        Default implementation returns None, which means the frontend
        will decide which fields to display.
        """
        return None

    def data(self):
        """
        Returns the data for the widget.
        """
        return {
            "object": self.obj.TYPE_ID,
            "filters": self.get_filters(),
            "limit": self.limit,
            "display_fields": self.get_display_fields(),
        }
