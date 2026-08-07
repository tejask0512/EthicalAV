"""
Korea AV Ethics Platform  (코리아 자율주행 윤리 플랫폼)
-----------------------------------------------------
A Moral-Machine-style web app, localized for South Korea, extended with
free-text NLP so we capture *why* people choose what they choose, not just
the click. Structure mirrors the reference Flask project:
  - session-based auth backed by SQLite
  - a background worker thread (here: re-aggregating NLP insights on a timer,
    instead of a scraper)
  - a small JSON API layer the frontend (and any dashboard) can poll
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
import sqlite3
import os
import re
import json
import random
import threading
import time
import secrets
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

from scenarios.scenario_engine import ScenarioEngine
from nlp.insights import analyze_comment, aggregate_insights
