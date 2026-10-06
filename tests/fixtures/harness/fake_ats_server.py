"""Realistic, 100% offline local Fake ATS HTTP server for testing job application agents.

Provides deterministic HTML application forms (single-page, multi-page wizard,
CAPTCHA challenges, login gates, and validation errors) and captures submissions
for automated empirical evaluation.
"""

import cgi
import io
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse


HTML_INDEX = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Fake ATS Test Harness</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f8fafc; color: #1e293b; }
    h1 { color: #0f172a; }
    .card { background: white; border-radius: 8px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }
    a { color: #2563eb; text-decoration: none; font-weight: 500; }
    a:hover { text-decoration: underline; }
    ul { line-height: 1.8; }
  </style>
</head>
<body>
  <div class="card">
    <h1>JobPilot Fake ATS Test Harness</h1>
    <p>Realistic mock endpoints for validating automated application agents.</p>
    <ul>
      <li><a href="/standard-job">Standard Job Application Form (Single Page)</a></li>
      <li><a href="/wizard/step1">Multi-Step Application Wizard (Step 1 of 3)</a></li>
      <li><a href="/greenhouse">Greenhouse ATS Archetype Fixture</a></li>
      <li><a href="/lever">Lever ATS Archetype Fixture</a></li>
      <li><a href="/workday/step1">Workday Multi-Step Wizard Archetype (Step 1 of 3)</a></li>
      <li><a href="/ashby">Ashby ATS Archetype Fixture</a></li>
      <li><a href="/challenge/captcha">CAPTCHA / Bot Protection Challenge</a></li>
      <li><a href="/challenge/login">Authentication / Login Gate</a></li>
      <li><a href="/thank-you">Submission Confirmation Page</a></li>
    </ul>
  </div>
</body>
</html>
"""

HTML_STANDARD_JOB = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Acme Corp — Senior Full Stack Engineer</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f1f5f9; padding: 40px; }
    .container { max-width: 680px; margin: 0 auto; background: white; border-radius: 12px; padding: 36px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    h1 { font-size: 24px; color: #0f172a; margin-top: 0; }
    .meta { color: #64748b; font-size: 14px; margin-bottom: 24px; }
    .field-group { margin-bottom: 20px; }
    label { display: block; font-size: 14px; font-weight: 600; color: #334155; margin-bottom: 6px; }
    .required-star { color: #ef4444; }
    input[type="text"], input[type="email"], input[type="tel"], select, textarea {
      width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 14px; box-sizing: border-box;
    }
    input:focus, select:focus, textarea:focus { border-color: #3b82f6; outline: none; }
    .radio-option { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-weight: normal; font-size: 14px; }
    .radio-option input { margin: 0; }
    .file-dropzone { border: 2px dashed #cbd5e1; border-radius: 8px; padding: 20px; text-align: center; background: #f8fafc; cursor: pointer; }
    .btn-submit { background: #2563eb; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; font-weight: 600; cursor: pointer; width: 100%; }
    .btn-submit:hover { background: #1d4ed8; }
    .alert-error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Senior Full Stack Engineer</h1>
    <div class="meta">Acme Corp &bull; Remote / Hybrid &bull; Full-Time</div>

    <!-- ERROR_BANNER_PLACEHOLDER -->

    <form id="application-form" method="POST" action="/standard-job/submit" enctype="multipart/form-data">
      
      <div class="field-group">
        <label for="first_name">First Name <span class="required-star">*</span></label>
        <input type="text" id="first_name" name="first_name" placeholder="Jane" required aria-required="true">
      </div>

      <div class="field-group">
        <label for="last_name">Last Name <span class="required-star">*</span></label>
        <input type="text" id="last_name" name="last_name" placeholder="Doe" required aria-required="true">
      </div>

      <div class="field-group">
        <label for="email">Email Address <span class="required-star">*</span></label>
        <input type="email" id="email" name="email" placeholder="jane.doe@example.com" required aria-required="true">
      </div>

      <div class="field-group">
        <label for="phone">Phone Number <span class="required-star">*</span></label>
        <input type="tel" id="phone" name="phone" placeholder="+1 (555) 000-0000" required aria-required="true">
      </div>

      <div class="field-group">
        <label for="linkedin_url">LinkedIn Profile URL</label>
        <input type="text" id="linkedin_url" name="linkedin_url" placeholder="https://linkedin.com/in/username">
      </div>

      <div class="field-group">
        <label for="portfolio_url">Portfolio / GitHub Website</label>
        <input type="text" id="portfolio_url" name="portfolio_url" placeholder="https://github.com/username">
      </div>

      <div class="field-group">
        <label for="resume_upload">Resume / CV (PDF or DOCX) <span class="required-star">*</span></label>
        <div class="file-dropzone">
          <input type="file" id="resume_upload" name="resume" accept=".pdf,.doc,.docx" required aria-required="true">
        </div>
      </div>

      <div class="field-group">
        <label id="work_auth_label">Are you legally authorized to work in this country? <span class="required-star">*</span></label>
        <div role="radiogroup" aria-labelledby="work_auth_label">
          <label class="radio-option">
            <input type="radio" name="work_auth" value="yes" required> Yes
          </label>
          <label class="radio-option">
            <input type="radio" name="work_auth" value="no"> No
          </label>
        </div>
      </div>

      <div class="field-group">
        <label id="visa_label">Will you now or in the future require visa sponsorship? <span class="required-star">*</span></label>
        <div role="radiogroup" aria-labelledby="visa_label">
          <label class="radio-option">
            <input type="radio" name="visa_sponsorship" value="yes" required> Yes
          </label>
          <label class="radio-option">
            <input type="radio" name="visa_sponsorship" value="no"> No
          </label>
        </div>
      </div>

      <div class="field-group">
        <label for="years_experience">Total Years of Relevant Experience <span class="required-star">*</span></label>
        <select id="years_experience" name="years_experience" required aria-required="true">
          <option value="">-- Please Select --</option>
          <option value="0-1">0-1 years</option>
          <option value="1-3">1-3 years</option>
          <option value="3-5">3-5 years</option>
          <option value="5-8">5-8 years</option>
          <option value="8+">8+ years</option>
        </select>
      </div>

      <div class="field-group">
        <label for="notice_period">Notice Period (in days)</label>
        <input type="text" id="notice_period" name="notice_period" placeholder="e.g. 30">
      </div>

      <div class="field-group">
        <label for="expected_salary">Desired Annual Salary / CTC</label>
        <input type="text" id="expected_salary" name="expected_salary" placeholder="e.g. $140,000">
      </div>

      <button type="submit" id="submit-application" class="btn-submit">Submit Application</button>
    </form>
  </div>
</body>
</html>
"""

HTML_GREENHOUSE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Stripe - Senior Backend Engineer (Greenhouse Application Portal)</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; padding: 40px; }
    .container { max-width: 680px; margin: 0 auto; background: white; border-radius: 12px; padding: 36px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    h1 { font-size: 24px; color: #0f172a; margin-top: 0; }
    .meta { color: #64748b; font-size: 14px; margin-bottom: 24px; }
    .field-group { margin-bottom: 20px; }
    label { display: block; font-size: 14px; font-weight: 600; color: #334155; margin-bottom: 6px; }
    .required-star { color: #ef4444; }
    input[type="text"], input[type="email"], input[type="tel"], select, textarea {
      width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 14px; box-sizing: border-box;
    }
    .file-dropzone { border: 2px dashed #cbd5e1; border-radius: 8px; padding: 20px; text-align: center; background: #f8fafc; }
    .btn-submit { background: #00875a; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; font-weight: 600; cursor: pointer; width: 100%; }
    .btn-submit:hover { background: #006644; }
    .alert-error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; }
  </style>
</head>
<body>
  <div class="container" id="app_body">
    <h1>Senior Backend Engineer</h1>
    <div class="meta">Stripe &bull; Greenhouse Portal &bull; Full-Time</div>
    <!-- ERROR_BANNER_PLACEHOLDER -->
    <form id="application_form" method="POST" action="/greenhouse/submit" enctype="multipart/form-data">
      <div class="field-group">
        <label for="first_name">First Name <span class="required-star">*</span></label>
        <input type="text" id="first_name" name="first_name" placeholder="Jane" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="last_name">Last Name <span class="required-star">*</span></label>
        <input type="text" id="last_name" name="last_name" placeholder="Doe" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="email">Email <span class="required-star">*</span></label>
        <input type="email" id="email" name="email" placeholder="jane@example.com" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="phone">Phone <span class="required-star">*</span></label>
        <input type="tel" id="phone" name="phone" placeholder="+1 555-0100" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="resume">Resume/CV <span class="required-star">*</span></label>
        <div class="file-dropzone">
          <input type="file" id="resume" name="resume" accept=".pdf,.docx" required aria-required="true">
        </div>
      </div>
      <div class="field-group">
        <label for="linkedin_url">LinkedIn Profile</label>
        <input type="text" id="linkedin_url" name="job_application[answers_attributes][0][text_value]" placeholder="https://linkedin.com/in/...">
      </div>
      <div class="field-group">
        <label for="portfolio_url">Website / GitHub</label>
        <input type="text" id="portfolio_url" name="job_application[answers_attributes][1][text_value]" placeholder="https://github.com/...">
      </div>
      <div class="field-group">
        <label for="work_auth">Are you legally authorized to work in this country? <span class="required-star">*</span></label>
        <select id="work_auth" name="work_auth" required aria-required="true">
          <option value="">-- Please Select --</option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
      </div>
      <div class="field-group">
        <label for="visa_sponsorship">Will you now or in the future require visa sponsorship? <span class="required-star">*</span></label>
        <select id="visa_sponsorship" name="visa_sponsorship" required aria-required="true">
          <option value="">-- Please Select --</option>
          <option value="no">No</option>
          <option value="yes">Yes</option>
        </select>
      </div>
      <div class="field-group">
        <label for="gender">Gender</label>
        <select id="gender" name="gender">
          <option value="">Select gender...</option>
          <option value="Female">Female</option>
          <option value="Male">Male</option>
          <option value="Decline">Decline to self-identify</option>
        </select>
      </div>
      <div class="field-group">
        <label for="veteran_status">Veteran Status</label>
        <select id="veteran_status" name="veteran_status">
          <option value="">Select status...</option>
          <option value="No">I am not a protected veteran</option>
          <option value="Yes">I identify as a protected veteran</option>
          <option value="Decline">I decline to self-identify</option>
        </select>
      </div>
      <button type="submit" id="submit_app" class="btn-submit">Submit Application</button>
    </form>
  </div>
</body>
</html>
"""

HTML_LEVER = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Figma — Product Engineer (Lever Application Portal)</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #fafafa; padding: 40px; }
    .application-container { max-width: 650px; margin: 0 auto; background: white; border-radius: 8px; padding: 32px; border: 1px solid #e5e7eb; }
    h2 { font-size: 22px; color: #111827; margin-top: 0; }
    .meta { color: #6b7280; font-size: 14px; margin-bottom: 24px; }
    .field-group { margin-bottom: 18px; }
    label { display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 6px; }
    input[type="text"], input[type="email"], input[type="tel"], select {
      width: 100%; padding: 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; box-sizing: border-box;
    }
    .template-btn-submit { background: #10b981; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 15px; font-weight: 600; cursor: pointer; width: 100%; }
    .template-btn-submit:hover { background: #059669; }
    .alert-error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; }
  </style>
</head>
<body>
  <div class="application-container">
    <h2>Apply for Product Engineer</h2>
    <div class="meta">Figma &bull; San Francisco, CA / Remote &bull; Lever Application</div>
    <!-- ERROR_BANNER_PLACEHOLDER -->
    <form class="application-form" action="/lever/submit" method="POST" enctype="multipart/form-data">
      <div class="field-group">
        <label for="resume">Resume/CV *</label>
        <input type="file" id="resume" name="resume" accept=".pdf,.docx" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="name">Full name *</label>
        <input type="text" id="name" name="name" placeholder="Full name" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="email">Email *</label>
        <input type="email" id="email" name="email" placeholder="you@domain.com" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="phone">Phone *</label>
        <input type="tel" id="phone" name="phone" placeholder="+1 555-0199" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="org">Current company</label>
        <input type="text" id="org" name="org" placeholder="Current employer">
      </div>
      <div class="field-group">
        <label for="linkedin_url">LinkedIn URL</label>
        <input type="text" id="linkedin_url" name="urls[LinkedIn]" placeholder="https://linkedin.com/in/...">
      </div>
      <div class="field-group">
        <label for="github_url">GitHub URL</label>
        <input type="text" id="github_url" name="urls[GitHub]" placeholder="https://github.com/...">
      </div>
      <div class="field-group">
        <label for="years_experience">Total years of relevant experience *</label>
        <select id="years_experience" name="years_experience" required aria-required="true">
          <option value="">Select...</option>
          <option value="1-3">1-3 years</option>
          <option value="3-5">3-5 years</option>
          <option value="5-8">5-8 years</option>
          <option value="8+">8+ years</option>
        </select>
      </div>
      <div class="field-group">
        <label for="notice_period">Notice period (in days)</label>
        <input type="text" id="notice_period" name="notice_period" placeholder="e.g. 30">
      </div>
      <button type="submit" id="lever-submit-btn" class="template-btn-submit">Submit application</button>
    </form>
  </div>
</body>
</html>
"""

HTML_WORKDAY_STEP1 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Salesforce Careers — Step 1: Personal Info (Workday)</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; padding: 40px; }
    .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .step-indicator { font-size: 13px; font-weight: bold; color: #0284c7; text-transform: uppercase; margin-bottom: 8px; }
    h2 { margin-top: 0; color: #111827; }
    .field-group { margin-bottom: 16px; }
    label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #374151; }
    input[type="text"], input[type="email"], input[type="tel"] { width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; box-sizing: border-box; }
    .btn { background: #0284c7; color: white; border: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; cursor: pointer; }
    .btn:hover { background: #0369a1; }
    .alert-error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="step-indicator">Step 1 of 3: My Information</div>
    <h2>Candidate Information</h2>
    <!-- ERROR_BANNER_PLACEHOLDER -->
    <form method="POST" action="/workday/step1">
      <div class="field-group">
        <label for="first_name">First Name *</label>
        <input type="text" id="first_name" name="first_name" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="last_name">Last Name *</label>
        <input type="text" id="last_name" name="last_name" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="email">Email *</label>
        <input type="email" id="email" name="email" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="phone">Phone Number *</label>
        <input type="tel" id="phone" name="phone" required aria-required="true">
      </div>
      <button type="submit" id="workday-next-step1" class="btn">Next: My Experience &rarr;</button>
    </form>
  </div>
</body>
</html>
"""

HTML_WORKDAY_STEP2 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Salesforce Careers — Step 2: Experience & Resume (Workday)</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; padding: 40px; }
    .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .step-indicator { font-size: 13px; font-weight: bold; color: #0284c7; text-transform: uppercase; margin-bottom: 8px; }
    h2 { margin-top: 0; color: #111827; }
    .field-group { margin-bottom: 16px; }
    label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #374151; }
    select, input[type="text"] { width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; box-sizing: border-box; }
    .btn { background: #0284c7; color: white; border: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; cursor: pointer; }
    .btn:hover { background: #0369a1; }
    .alert-error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="step-indicator">Step 2 of 3: My Experience</div>
    <h2>Experience & Resume</h2>
    <!-- ERROR_BANNER_PLACEHOLDER -->
    <form method="POST" action="/workday/step2" enctype="multipart/form-data">
      <div class="field-group">
        <label for="resume">Resume / CV *</label>
        <input type="file" id="resume" name="resume" accept=".pdf,.docx" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="years_experience">Years of Relevant Experience *</label>
        <select id="years_experience" name="years_experience" required aria-required="true">
          <option value="">Select experience...</option>
          <option value="1-3">1-3 years</option>
          <option value="3-5">3-5 years</option>
          <option value="5-8">5-8 years</option>
        </select>
      </div>
      <div class="field-group">
        <label for="work_auth">Are you legally authorized to work in this country? *</label>
        <select id="work_auth" name="work_auth" required aria-required="true">
          <option value="">--</option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
      </div>
      <button type="submit" id="workday-next-step2" class="btn">Next: Review & Submit &rarr;</button>
    </form>
  </div>
</body>
</html>
"""

HTML_WORKDAY_STEP3 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Salesforce Careers — Step 3: Review Application (Workday)</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; padding: 40px; }
    .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .step-indicator { font-size: 13px; font-weight: bold; color: #0284c7; text-transform: uppercase; margin-bottom: 8px; }
    h2 { margin-top: 0; color: #111827; }
    .summary-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 20px; font-size: 14px; }
    .btn-submit { background: #16a34a; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; cursor: pointer; width: 100%; font-size: 16px; }
    .btn-submit:hover { background: #15803d; }
  </style>
</head>
<body>
  <div class="container">
    <div class="step-indicator">Step 3 of 3: Review Application</div>
    <h2>Review & Submit</h2>
    <div class="summary-card">
      <p><strong>Status:</strong> Ready for Submission</p>
      <p><strong>Candidate Details:</strong> Received</p>
      <p><strong>Resume:</strong> Attached</p>
    </div>
    <form method="POST" action="/workday/step3">
      <input type="hidden" name="confirmed" value="true">
      <button type="submit" id="workday-final-submit" class="btn-submit">Submit Application</button>
    </form>
  </div>
</body>
</html>
"""

HTML_ASHBY = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ramp — Staff Software Engineer (Ashby Application Portal)</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #fafafa; padding: 40px; }
    ._ashby_application_container { max-width: 640px; margin: 0 auto; background: white; border-radius: 12px; padding: 36px; border: 1px solid #eaeaea; }
    h1 { font-size: 22px; color: #18181b; margin-top: 0; }
    .meta { color: #71717a; font-size: 14px; margin-bottom: 24px; }
    .field-group { margin-bottom: 18px; }
    label { display: block; font-size: 13px; font-weight: 600; color: #27272a; margin-bottom: 6px; }
    input[type="text"], input[type="email"], input[type="tel"], select {
      width: 100%; padding: 10px; border: 1px solid #e4e4e7; border-radius: 6px; font-size: 14px; box-sizing: border-box;
    }
    .ashby-btn-primary { background: #2563eb; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 15px; font-weight: 600; cursor: pointer; width: 100%; }
    .ashby-btn-primary:hover { background: #1d4ed8; }
    .alert-error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; }
  </style>
</head>
<body>
  <div class="_ashby_application_container">
    <h1>Staff Software Engineer</h1>
    <div class="meta">Ramp &bull; New York, NY / Remote &bull; Ashby Portal</div>
    <!-- ERROR_BANNER_PLACEHOLDER -->
    <form class="_ashby_form" action="/ashby/submit" method="POST" enctype="multipart/form-data">
      <div class="field-group">
        <label for="first_name">First Name *</label>
        <input type="text" id="first_name" name="first_name" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="last_name">Last Name *</label>
        <input type="text" id="last_name" name="last_name" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="email">Email *</label>
        <input type="email" id="email" name="email" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="phone">Phone *</label>
        <input type="tel" id="phone" name="phone" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="resume">Resume *</label>
        <input type="file" id="resume" name="resume" accept=".pdf,.docx" required aria-required="true">
      </div>
      <div class="field-group">
        <label for="work_auth">Are you legally authorized to work in this country? *</label>
        <select id="work_auth" name="work_auth" required aria-required="true">
          <option value="">--</option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
      </div>
      <div class="field-group">
        <label for="visa_sponsorship">Will you now or in the future require visa sponsorship? *</label>
        <select id="visa_sponsorship" name="visa_sponsorship" required aria-required="true">
          <option value="">--</option>
          <option value="no">No</option>
          <option value="yes">Yes</option>
        </select>
      </div>
      <div class="field-group">
        <label for="notice_period">Notice period (in days)</label>
        <input type="text" id="notice_period" name="notice_period" placeholder="30">
      </div>
      <div class="field-group">
        <label for="expected_salary">Desired Annual Salary / CTC</label>
        <input type="text" id="expected_salary" name="expected_salary" placeholder="$150,000">
      </div>
      <button type="submit" id="ashby-submit" class="ashby-btn-primary">Submit Application</button>
    </form>
  </div>
</body>
</html>
"""

HTML_WIZARD_STEP1 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Apex Dynamics Application — Step 1: Personal Info</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; padding: 40px; }
    .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .step-indicator { font-size: 13px; font-weight: bold; color: #2563eb; text-transform: uppercase; margin-bottom: 8px; }
    h2 { margin-top: 0; color: #0f172a; }
    .field-group { margin-bottom: 16px; }
    label { display: block; font-size: 14px; font-weight: 600; margin-bottom: 4px; color: #334155; }
    input[type="text"], input[type="email"], input[type="tel"] { width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; }
    .btn { background: #2563eb; color: white; border: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; cursor: pointer; }
  </style>
</head>
<body>
  <div class="container">
    <div class="step-indicator">Step 1 of 3</div>
    <h2>Contact & Personal Details</h2>
    <form method="POST" action="/wizard/step1">
      <div class="field-group">
        <label for="first_name">First Name *</label>
        <input type="text" id="first_name" name="first_name" required>
      </div>
      <div class="field-group">
        <label for="last_name">Last Name *</label>
        <input type="text" id="last_name" name="last_name" required>
      </div>
      <div class="field-group">
        <label for="email">Email Address *</label>
        <input type="email" id="email" name="email" required>
      </div>
      <div class="field-group">
        <label for="phone">Phone Number *</label>
        <input type="tel" id="phone" name="phone" required>
      </div>
      <button type="submit" id="btn-next-step1" class="btn">Next: Experience & Resume &rarr;</button>
    </form>
  </div>
</body>
</html>
"""

HTML_WIZARD_STEP2 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Apex Dynamics Application — Step 2: Experience & Resume</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; padding: 40px; }
    .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .step-indicator { font-size: 13px; font-weight: bold; color: #2563eb; text-transform: uppercase; margin-bottom: 8px; }
    h2 { margin-top: 0; color: #0f172a; }
    .field-group { margin-bottom: 16px; }
    label { display: block; font-size: 14px; font-weight: 600; margin-bottom: 4px; color: #334155; }
    select, input[type="text"] { width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; }
    .btn { background: #2563eb; color: white; border: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; cursor: pointer; }
  </style>
</head>
<body>
  <div class="container">
    <div class="step-indicator">Step 2 of 3</div>
    <h2>Professional Experience & Resume</h2>
    <form method="POST" action="/wizard/step2" enctype="multipart/form-data">
      <div class="field-group">
        <label for="resume_file">Upload Resume *</label>
        <input type="file" id="resume_file" name="resume" accept=".pdf,.docx" required>
      </div>
      <div class="field-group">
        <label for="years_experience">Years of Experience *</label>
        <select id="years_experience" name="years_experience" required>
          <option value="">Select...</option>
          <option value="1-3">1-3 years</option>
          <option value="3-5">3-5 years</option>
          <option value="5+">5+ years</option>
        </select>
      </div>
      <div class="field-group">
        <label for="current_company">Current Employer</label>
        <input type="text" id="current_company" name="current_company" placeholder="Company Name">
      </div>
      <button type="submit" id="btn-next-step2" class="btn">Next: Review & Submit &rarr;</button>
    </form>
  </div>
</body>
</html>
"""

HTML_WIZARD_STEP3 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Apex Dynamics Application — Step 3: Review & Submit</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; padding: 40px; }
    .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .step-indicator { font-size: 13px; font-weight: bold; color: #2563eb; text-transform: uppercase; margin-bottom: 8px; }
    h2 { margin-top: 0; color: #0f172a; }
    .summary-box { background: #f1f5f9; padding: 16px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; }
    .btn-submit { background: #16a34a; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; cursor: pointer; width: 100%; font-size: 16px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="step-indicator">Step 3 of 3</div>
    <h2>Review Your Application</h2>
    <div class="summary-box">
      <p><strong>Candidate:</strong> Jane Doe (jane.doe@example.com)</p>
      <p><strong>Resume:</strong> Attached</p>
      <p>Please review your details before confirming submission.</p>
    </div>
    <form method="POST" action="/wizard/step3">
      <input type="hidden" name="confirmed" value="true">
      <button type="submit" id="btn-final-submit" class="btn-submit">Submit Application</button>
    </form>
  </div>
</body>
</html>
"""

HTML_CAPTCHA_CHALLENGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Security Verification</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f1f5f9; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
    .challenge-card { background: white; border-radius: 8px; padding: 32px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 400px; text-align: center; }
    .cf-turnstile-wrapper { border: 1px solid #d1d5db; border-radius: 4px; padding: 16px; margin: 20px 0; background: #fafafa; display: flex; align-items: center; gap: 12px; }
    .btn-solve { background: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
  </style>
</head>
<body>
  <div class="challenge-card">
    <h2>Verifying you are human</h2>
    <p>Please solve the challenge below to continue to the application.</p>
    <div class="cf-turnstile-wrapper" id="mock-cf-turnstile">
      <input type="checkbox" id="challenge-checkbox">
      <label for="challenge-checkbox">I am not a robot</label>
    </div>
    <form method="POST" action="/challenge/captcha/verify">
      <input type="hidden" name="solved" id="solved-flag" value="false">
      <button type="submit" id="btn-verify-challenge" class="btn-solve" onclick="document.getElementById('solved-flag').value='true'">Continue to Application</button>
    </form>
  </div>
</body>
</html>
"""

HTML_LOGIN_GATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Candidate Login Required</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
    .login-card { background: white; border-radius: 8px; padding: 32px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); width: 360px; }
    h2 { margin-top: 0; }
    .field { margin-bottom: 16px; }
    label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
    input { width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box; }
    .btn-login { width: 100%; background: #0f172a; color: white; padding: 10px; border: none; border-radius: 4px; font-weight: 600; cursor: pointer; }
  </style>
</head>
<body>
  <div class="login-card">
    <h2>Sign in to Apply</h2>
    <p style="font-size: 13px; color: #64748b;">Please authenticate with your company candidate account.</p>
    <form method="POST" action="/challenge/login">
      <div class="field">
        <label for="login-email">Email</label>
        <input type="email" id="login-email" name="email" required>
      </div>
      <div class="field">
        <label for="login-password">Password</label>
        <input type="password" id="login-password" name="password" required>
      </div>
      <button type="submit" id="btn-login-submit" class="btn-login">Sign In & Continue</button>
    </form>
  </div>
</body>
</html>
"""

HTML_THANK_YOU = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Application Received — Acme Corp</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0fdf4; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
    .success-card { background: white; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; max-width: 480px; }
    .success-icon { font-size: 48px; color: #16a34a; margin-bottom: 16px; }
    h1 { color: #14532d; margin: 0 0 12px 0; font-size: 24px; }
    p { color: #374151; font-size: 15px; line-height: 1.5; }
    .ref-code { background: #f1f5f9; padding: 6px 12px; border-radius: 4px; font-family: monospace; font-size: 14px; font-weight: bold; }
  </style>
</head>
<body>
  <div class="success-card">
    <div class="success-icon">&check;</div>
    <h1 id="confirmation-header">Thank you for your application!</h1>
    <p id="confirmation-text">We have successfully received your application for <strong>Senior Full Stack Engineer</strong>.</p>
    <p>Reference Code: <span id="app-reference" class="ref-code">APP-JP-98765</span></p>
  </div>
</body>
</html>
"""


class FakeATSHandler(BaseHTTPRequestHandler):
    """HTTP request handler routing fake ATS test pages and capturing submissions."""

    server: "FakeATSServer"

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard stdout logging during test runs
        pass

    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = url.path.rstrip("/")

        if path == "" or path == "/index":
            self._send_html(HTML_INDEX)
        elif path == "/standard-job":
            self._send_html(HTML_STANDARD_JOB.replace("<!-- ERROR_BANNER_PLACEHOLDER -->", ""))
        elif path == "/wizard/step1":
            self._send_html(HTML_WIZARD_STEP1)
        elif path == "/wizard/step2":
            self._send_html(HTML_WIZARD_STEP2)
        elif path == "/wizard/step3":
            self._send_html(HTML_WIZARD_STEP3)
        elif path == "/challenge/captcha":
            self._send_html(HTML_CAPTCHA_CHALLENGE)
        elif path == "/challenge/login":
            self._send_html(HTML_LOGIN_GATE)
        elif path == "/greenhouse":
            self._send_html(HTML_GREENHOUSE.replace("<!-- ERROR_BANNER_PLACEHOLDER -->", ""))
        elif path == "/lever":
            self._send_html(HTML_LEVER.replace("<!-- ERROR_BANNER_PLACEHOLDER -->", ""))
        elif path == "/workday/step1":
            self._send_html(HTML_WORKDAY_STEP1.replace("<!-- ERROR_BANNER_PLACEHOLDER -->", ""))
        elif path == "/workday/step2":
            self._send_html(HTML_WORKDAY_STEP2.replace("<!-- ERROR_BANNER_PLACEHOLDER -->", ""))
        elif path == "/workday/step3":
            self._send_html(HTML_WORKDAY_STEP3)
        elif path == "/ashby":
            self._send_html(HTML_ASHBY.replace("<!-- ERROR_BANNER_PLACEHOLDER -->", ""))
        elif path == "/thank-you":
            qs = parse_qs(url.query)
            ref_code = qs.get("ref", ["APP-JP-98765"])[0]
            rendered_thank_you = HTML_THANK_YOU.replace("APP-JP-98765", ref_code)
            self._send_html(rendered_thank_you)
        elif path == "/api/last-submission":
            owner = getattr(self.server, "owner", None)
            self._send_json(owner.last_submission if owner else {})
        elif path == "/api/history":
            owner = getattr(self.server, "owner", None)
            self._send_json(owner.submissions_history if owner else [])
        else:
            self.send_error(404, "Page Not Found")

    def do_POST(self) -> None:
        url = urlparse(self.path)
        path = url.path.rstrip("/")

        content_type = self.headers.get("Content-Type", "")
        form_data: Dict[str, Any] = {}
        files_data: Dict[str, Dict[str, Any]] = {}

        if "multipart/form-data" in content_type:
            # Parse multipart file upload using FieldStorage
            env = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers["Content-Type"],
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            }
            fs = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=env)
            for key in fs.keys():
                item = fs[key]
                if item.filename:
                    # Captured file upload
                    files_data[key] = {
                        "filename": item.filename,
                        "size": len(item.value),
                        "content_type": item.type,
                    }
                    form_data[key] = f"[FILE: {item.filename}]"
                else:
                    form_data[key] = item.value
        else:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            parsed = parse_qs(body)
            for k, v in parsed.items():
                form_data[k] = v[0] if len(v) == 1 else v

        # Store parsed submission on server
        record = {
            "endpoint": path,
            "fields": form_data,
            "files": files_data,
            "headers": dict(self.headers),
        }
        owner = getattr(self.server, "owner", None)
        if owner:
            owner.last_submission = record
            owner.submissions_history.append(record)

        if path == "/standard-job/submit":
            # Validation check: verify mandatory fields
            required_fields = ["first_name", "last_name", "email", "phone", "work_auth", "visa_sponsorship", "years_experience"]
            missing = [f for f in required_fields if not form_data.get(f)]
            if not files_data.get("resume"):
                missing.append("resume (file)")

            if missing:
                error_msg = f'<div id="form-errors" class="alert-error"><strong>Submission Error:</strong> Please provide all required fields: {", ".join(missing)}</div>'
                rendered = HTML_STANDARD_JOB.replace("<!-- ERROR_BANNER_PLACEHOLDER -->", error_msg)
                self._send_html(rendered, status=400)
            else:
                # Redirect to confirmation page
                self.send_response(303)
                self.send_header("Location", "/thank-you?status=success&ref=APP-JP-98765")
                self.end_headers()

        elif path == "/wizard/step1":
            self.send_response(303)
            self.send_header("Location", "/wizard/step2")
            self.end_headers()

        elif path == "/wizard/step2":
            self.send_response(303)
            self.send_header("Location", "/wizard/step3")
            self.end_headers()

        elif path == "/wizard/step3":
            self.send_response(303)
            self.send_header("Location", "/thank-you?status=success&ref=APP-WIZARD-1122")
            self.end_headers()

        elif path == "/greenhouse/submit":
            required_fields = ["first_name", "last_name", "email", "phone", "work_auth", "visa_sponsorship"]
            missing = [f for f in required_fields if not form_data.get(f)]
            if not files_data.get("resume"):
                missing.append("resume (file)")

            if missing:
                error_msg = f'<div id="form-errors" class="alert-error"><strong>Submission Error:</strong> Please provide all required fields: {", ".join(missing)}</div>'
                rendered = HTML_GREENHOUSE.replace("<!-- ERROR_BANNER_PLACEHOLDER -->", error_msg)
                self._send_html(rendered, status=400)
            else:
                self.send_response(303)
                self.send_header("Location", "/thank-you?status=success&ref=GH-CONF-12345")
                self.end_headers()

        elif path == "/lever/submit":
            required_fields = ["name", "email", "phone", "years_experience"]
            missing = [f for f in required_fields if not form_data.get(f)]
            if not files_data.get("resume"):
                missing.append("resume (file)")

            if missing:
                error_msg = f'<div id="form-errors" class="alert-error"><strong>Submission Error:</strong> Please provide all required fields: {", ".join(missing)}</div>'
                rendered = HTML_LEVER.replace("<!-- ERROR_BANNER_PLACEHOLDER -->", error_msg)
                self._send_html(rendered, status=400)
            else:
                self.send_response(303)
                self.send_header("Location", "/thank-you?status=success&ref=LEV-CONF-67890")
                self.end_headers()

        elif path == "/workday/step1":
            required_fields = ["first_name", "last_name", "email", "phone"]
            missing = [f for f in required_fields if not form_data.get(f)]
            if missing:
                error_msg = f'<div id="form-errors" class="alert-error"><strong>Error:</strong> Please provide all required fields: {", ".join(missing)}</div>'
                rendered = HTML_WORKDAY_STEP1.replace("<!-- ERROR_BANNER_PLACEHOLDER -->", error_msg)
                self._send_html(rendered, status=400)
            else:
                self.send_response(303)
                self.send_header("Location", "/workday/step2")
                self.end_headers()

        elif path == "/workday/step2":
            required_fields = ["years_experience", "work_auth"]
            missing = [f for f in required_fields if not form_data.get(f)]
            if not files_data.get("resume"):
                missing.append("resume (file)")

            if missing:
                error_msg = f'<div id="form-errors" class="alert-error"><strong>Error:</strong> Please provide all required fields: {", ".join(missing)}</div>'
                rendered = HTML_WORKDAY_STEP2.replace("<!-- ERROR_BANNER_PLACEHOLDER -->", error_msg)
                self._send_html(rendered, status=400)
            else:
                self.send_response(303)
                self.send_header("Location", "/workday/step3")
                self.end_headers()

        elif path == "/workday/step3":
            self.send_response(303)
            self.send_header("Location", "/thank-you?status=success&ref=WD-CONF-77889")
            self.end_headers()

        elif path == "/ashby/submit":
            required_fields = ["first_name", "last_name", "email", "phone", "work_auth", "visa_sponsorship"]
            missing = [f for f in required_fields if not form_data.get(f)]
            if not files_data.get("resume"):
                missing.append("resume (file)")

            if missing:
                error_msg = f'<div id="form-errors" class="alert-error"><strong>Submission Error:</strong> Please provide all required fields: {", ".join(missing)}</div>'
                rendered = HTML_ASHBY.replace("<!-- ERROR_BANNER_PLACEHOLDER -->", error_msg)
                self._send_html(rendered, status=400)
            else:
                self.send_response(303)
                self.send_header("Location", "/thank-you?status=success&ref=ASH-CONF-99001")
                self.end_headers()

        elif path == "/challenge/captcha/verify":
            self.send_response(303)
            self.send_header("Location", "/standard-job?challenge=passed")
            self.end_headers()

        elif path == "/challenge/login":
            self.send_response(303)
            self.send_header("Location", "/standard-job?auth=logged_in")
            self.end_headers()

        else:
            self.send_error(404, "Endpoint Not Found")

    def _send_html(self, html: str, status: int = 200) -> None:
        encoded = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, data: Any, status: int = 200) -> None:
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class FakeATSServer:
    """Threaded local HTTP server for mock application portals."""

    def __init__(self, port: int = 0, host: str = "127.0.0.1") -> None:
        self.host = host
        self.requested_port = port
        self.httpd: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.port: int = 0
        self.base_url: str = ""
        self.last_submission: Optional[Dict[str, Any]] = None
        self.submissions_history: List[Dict[str, Any]] = []

    def start(self) -> str:
        """Starts the fake ATS HTTP server in a background daemon thread."""
        server_address = (self.host, self.requested_port)
        
        # Instantiate server and assign backreference
        self.httpd = HTTPServer(server_address, FakeATSHandler)
        self.httpd.owner = self  # type: ignore[attr-defined]
        self.port = self.httpd.server_port
        self.base_url = f"http://{self.host}:{self.port}"

        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        os.environ["JOBPILOT_ALLOW_LOCAL_TESTING"] = "1"
        return self.base_url

    def stop(self) -> None:
        """Stops the fake ATS HTTP server cleanly."""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None

    def reset(self) -> None:
        """Clears captured submission state."""
        self.last_submission = None
        self.submissions_history.clear()

    def __enter__(self) -> "FakeATSServer":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()
