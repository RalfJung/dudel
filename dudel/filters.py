from flask.ext.login import current_user
from flask.ext.babel import format_date, format_time, get_locale

import datetime as dt
import pytz
import json as jsonlib

from dudel import app, ICONS, default_timezone
from dudel.forms import LoginForm, LanguageForm
from dudel.models import PollType
from dudel.util import PartialDateTime


date_formats = {'de': 'EEE, dd. MMM'}


def get_timezone(ref):
    if isinstance(ref, dt.tzinfo):
        return ref
    elif hasattr(ref, "timezone"):
        return ref.timezone
    elif ref == current_user:
        return default_timezone
    return None


@app.template_filter()
def in_timezone_of(datetime, ref):
    timezone = get_timezone(ref)
    return pytz.utc.localize(datetime).astimezone(timezone) if timezone else datetime


@app.template_filter()
def time(datetime, ref=current_user):
    time = in_timezone_of(datetime, ref).time()
    return format_time(time, 'HH:mm', rebase=False)


@app.template_filter()
def date(datetime, ref=current_user, year=False):
    fmt = date_formats.get(get_locale().language, 'EEE, dd MMM') + (' yyyy' if year else '')
    date = in_timezone_of(datetime, ref).date()
    return format_date(date, fmt, rebase=False)


@app.template_filter()
def datetime(datetime, ref=current_user):
    return date(datetime, ref) + ', ' + time(datetime, ref)


@app.template_filter()
def timestamp(datetime, ref=current_user):
    time = in_timezone_of(datetime, ref).time()
    return str(time)


@app.template_filter()
def json(string):
    return jsonlib.dumps(string)


def get_current_timezone():
    return current_user.timezone if current_user.is_authenticated() else default_timezone


@app.template_filter()
def group_title(obj, poll):
    if isinstance(obj, PartialDateTime):
        return obj.format()
    else:
        return obj


@app.template_filter()
def transpose(matrix):
    return [list(i) for i in zip(*matrix)]


@app.context_processor
def inject():
    from dudel.views import get_locale
    return dict(
        ICONS=ICONS,
        login_form=LoginForm(),
        lang_form=LanguageForm(),
        enumerate=enumerate,
        lang=get_locale(),
        current_timezone=get_current_timezone(),
        default_timezone=default_timezone,
        PollType=PollType
        )
