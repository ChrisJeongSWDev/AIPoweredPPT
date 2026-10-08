#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the Two-Pass Review Workflow & fallback mechanisms."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from aippt.canvas.app import app, generate_live
from aippt.canvas.pin import load_pin
from aippt.adapters.ai_adapter import CliWorkerError


class TestReviewWorkflow(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_invalid_reviewer_model_returns_422(self):
        """POSTing an invalid reviewer_model should return 422 Unprocessable Entity."""
        response = self.client.post(
            "/api/generate",
            json={"prompt": "Test prompt", "review": True, "reviewer_model": "non_existent_model"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("invalid reviewer_model", response.json().get("detail", ""))

    def test_generate_live_reviewer_exception_fallback(self):
        """If reviewer raises an exception in generate_live, return the 1st pass draft."""
        pin = load_pin()
        mock_initial_obj = {
            "title": "Initial Title",
            "elements": [
                {
                    "id": "box1",
                    "type": "textbox",
                    "x": 60.0,
                    "y": 120.0,
                    "w": 300.0,
                    "h": 100.0,
                    "fill": None,
                    "text": {
                        "align": "LEFT",
                        "valign": "TOP",
                        "paragraphs": [{"runs": [{"t": "Initial content", "size": 16, "bold": True, "color": "#1A1A1A"}]}],
                    },
                }
            ],
        }

        def mock_complete_json(*args, **kwargs):
            if not hasattr(mock_complete_json, "called"):
                mock_complete_json.called = True
                return mock_initial_obj
            raise CliWorkerError("Reviewer process crashed")

        with patch("aippt.canvas.app.CliWorkerClient.complete_json", side_effect=mock_complete_json):
            result = asyncio.run(
                generate_live("Test prompt", pin, profile="sonnet", review=True, reviewer_model="gpt-5.6-terra")
            )

        self.assertEqual(result["elements"][0]["id"], "box1")
        self.assertEqual(result["elements"][0]["text"]["paragraphs"][0]["runs"][0]["t"], "Initial content")
        self.assertEqual(result.get("_meta"), {"review_applied": False})

    def test_generate_live_reviewer_invalid_ir_fallback(self):
        """If reviewer returns a draft that fails canvas validation (e.g. invalid bounds), fallback to 1st pass."""
        pin = load_pin()
        mock_initial_obj = {
            "title": "Initial Title",
            "elements": [
                {
                    "id": "box1",
                    "type": "textbox",
                    "x": 60.0,
                    "y": 120.0,
                    "w": 300.0,
                    "h": 100.0,
                    "fill": None,
                    "text": {
                        "align": "LEFT",
                        "valign": "TOP",
                        "paragraphs": [{"runs": [{"t": "Initial content", "size": 16, "bold": True, "color": "#1A1A1A"}]}],
                    },
                }
            ],
        }
        mock_invalid_reviewed_obj = {
            "title": "Reviewed Title",
            "elements": [
                {
                    "id": "box1",
                    "type": "textbox",
                    "x": -999.0,
                    "y": -999.0,
                    "w": 300.0,
                    "h": 100.0,
                    "fill": None,
                }
            ],
        }

        calls = [mock_initial_obj, mock_invalid_reviewed_obj]

        def mock_complete_json(*args, **kwargs):
            return calls.pop(0)

        with patch("aippt.canvas.app.CliWorkerClient.complete_json", side_effect=mock_complete_json):
            result = asyncio.run(
                generate_live("Test prompt", pin, profile="sonnet", review=True, reviewer_model="gpt-5.6-terra")
            )

        self.assertEqual(result["elements"][0]["x"], 60.0)
        self.assertEqual(result.get("_meta"), {"review_applied": False})

    def test_generate_live_reviewer_success(self):
        """If reviewer returns a valid draft, return reviewed draft with review_applied: True."""
        pin = load_pin()
        mock_initial_obj = {
            "title": "Initial Title",
            "elements": [
                {
                    "id": "box1",
                    "type": "textbox",
                    "x": 60.0,
                    "y": 120.0,
                    "w": 300.0,
                    "h": 100.0,
                    "fill": None,
                    "text": {
                        "align": "LEFT",
                        "valign": "TOP",
                        "paragraphs": [{"runs": [{"t": "Initial content", "size": 16, "bold": True, "color": "#1A1A1A"}]}],
                    },
                }
            ],
        }
        mock_valid_reviewed_obj = {
            "title": "Reviewed Title",
            "elements": [
                {
                    "id": "box1",
                    "type": "textbox",
                    "x": 60.0,
                    "y": 120.0,
                    "w": 300.0,
                    "h": 100.0,
                    "fill": None,
                    "text": {
                        "align": "LEFT",
                        "valign": "TOP",
                        "paragraphs": [{"runs": [{"t": "Reviewed content", "size": 16, "bold": True, "color": "#1A1A1A"}]}],
                    },
                }
            ],
        }

        calls = [mock_initial_obj, mock_valid_reviewed_obj]

        def mock_complete_json(*args, **kwargs):
            return calls.pop(0)

        with patch("aippt.canvas.app.CliWorkerClient.complete_json", side_effect=mock_complete_json):
            result = asyncio.run(
                generate_live("Test prompt", pin, profile="sonnet", review=True, reviewer_model="gpt-5.6-terra")
            )

        self.assertEqual(result["title"], "Reviewed Title")
        self.assertEqual(result.get("_meta"), {"review_applied": True})


if __name__ == "__main__":
    unittest.main()
