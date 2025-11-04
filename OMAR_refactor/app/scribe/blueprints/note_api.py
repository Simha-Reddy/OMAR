from __future__ import annotations
import os
from typing import List, Dict, Any, Optional

from flask import Blueprint, request, jsonify, current_app


bp = Blueprint('scribe_note', __name__)


def _read_system_preface() -> str:
	"""Load the scribe system preface from prompts folder.
	Falls back to a conservative default when file/env not present.
	"""
	try:
		# Prefer explicit path under app/scribe/prompts
		base_dir = os.path.dirname(os.path.dirname(__file__))  # .../app/scribe
		prompts_dir = os.path.join(base_dir, 'prompts')
		pref_path = os.path.join(prompts_dir, 'scribe_system.md')
		if os.path.exists(pref_path):
			with open(pref_path, 'r', encoding='utf-8') as f:
				return f.read().strip()
	except Exception:
		pass
	return (
		"You are an assistant for drafting clinical notes from transcripts.\n"
		"- Structure text into clear sections (Subjective, Objective, Assessment, Plan) when possible.\n"
		"- Keep language neutral and avoid clinical recommendations.\n"
		"- Insert placeholders for missing details rather than inventing facts."
	)


def _azure_chat(messages: List[Dict[str, Any]], *, deployment: Optional[str] = None, temperature: float = 0.2) -> Optional[str]:
	"""Attempt Azure OpenAI chat call. Returns None when not configured or on failure."""
	try:
		from openai import AzureOpenAI  # type: ignore
	except Exception:
		return None

	api_key = os.getenv('AZURE_OPENAI_API_KEY')
	endpoint = os.getenv('AZURE_OPENAI_ENDPOINT') or os.getenv('AZURE_ENDPOINT')
	api_version = os.getenv('AZURE_API_VERSION', '2024-02-15-preview')
	model = deployment or os.getenv('AZURE_DEPLOYMENT_NAME')
	if not api_key or not endpoint or not model:
		return None

	try:
		client = AzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version=api_version)
		resp = client.chat.completions.create(
			model=model,
			temperature=temperature,
			messages=messages,  # type: ignore[arg-type]
		)
		return (resp.choices[0].message.content or '').strip()
	except Exception:
		return None


@bp.post('/create_note')
def create_note():
	"""Create/refresh a draft note from a prompt, transcript, and current draft.

	Body JSON: {
	  prompt: str,            // chosen user prompt/template
	  transcript: str,        // current transcript text (server-side preferred)
	  draft: str,             // current draft contents (may be empty)
	  model?: str,            // optional Azure deployment name
	  temperature?: float     // optional temperature
	}

	Returns JSON: { note: string, messages: array }
	"""
	try:
		data = request.get_json(silent=True) or {}
		# Accept multiple client field names for compatibility
		user_prompt = str(
			(data.get('prompt') or data.get('prompt_text') or '')
		).strip()
		transcript = str(data.get('transcript') or '').strip()
		current_draft = str(
			(data.get('draft') or data.get('current_draft') or '')
		).strip()
		deployment = str(data.get('model') or '').strip() or None
		t_raw = data.get('temperature')
		try:
			temperature = float(t_raw) if isinstance(t_raw, (int, float, str)) and str(t_raw).strip() != '' else 0.2
		except Exception:
			temperature = 0.2

		if not user_prompt and not transcript and not current_draft:
			return jsonify({ 'error': 'Nothing to draft: provide a prompt, transcript, or existing draft.' }), 400

		system_preface = _read_system_preface()
		# Compose a single user message including the chosen prompt, transcript, and current draft
		user_content = []
		if user_prompt:
			user_content.append(f"Instruction/Prompt:\n{user_prompt}\n")
		if transcript:
			user_content.append(f"Transcript:\n{transcript}\n")
		if current_draft:
			user_content.append(f"Current Draft:\n{current_draft}\n")
		if not user_content:
			user_content.append("No content provided.")
		messages: List[Dict[str, str]] = [
			{ 'role': 'system', 'content': system_preface },
			{ 'role': 'user', 'content': "\n\n".join(user_content) },
		]

		reply = _azure_chat(messages, deployment=deployment, temperature=temperature)
		if reply is None:
			# Dev fallback: provide an echo-style synthesized draft
			synthesized = []
			if user_prompt:
				synthesized.append(f"[Prompt]\n{user_prompt}")
			if transcript:
				synthesized.append(f"[Transcript]\n{transcript[:2000]}")
			if current_draft:
				synthesized.append(f"[Prev Draft]\n{current_draft[:2000]}")
			reply = "\n\n".join(synthesized) or "[Empty draft]"

		return jsonify({ 'note': reply, 'messages': messages })
	except Exception as e:
		return jsonify({ 'error': f'failed to create note: {e}' }), 500


@bp.post('/chat_feedback')
def chat_feedback():
	"""Follow-up chat for note refinement.

	Body JSON: { messages: [ { role, content }, ... ], model?: str, temperature?: float }
	Returns: { reply: string }
	"""
	try:
		data = request.get_json(silent=True) or {}
		messages_in = data.get('messages') or []
		deployment = str(data.get('model') or '').strip() or None
		t_raw = data.get('temperature')
		try:
			temperature = float(t_raw) if isinstance(t_raw, (int, float, str)) and str(t_raw).strip() != '' else 0.2
		except Exception:
			temperature = 0.2

		# Normalize and prepend system preface
		norm: List[Dict[str, str]] = []
		system_preface = _read_system_preface()
		norm.append({ 'role': 'system', 'content': system_preface })
		if isinstance(messages_in, list):
			for m in messages_in:
				try:
					role = str(m.get('role') or '').strip() or 'user'
					content = str(m.get('content') or '').strip()
					if content:
						norm.append({ 'role': role, 'content': content })
				except Exception:
					continue

		reply = _azure_chat(norm, deployment=deployment, temperature=temperature)
		if reply is None:
			# Fallback: echo last user message
			last_user = next((m['content'] for m in reversed(norm) if m.get('role') == 'user' and m.get('content')), '')
			reply = f"[DEV ECHO] {last_user[:2000]}"

		return jsonify({ 'reply': reply })
	except Exception as e:
		return jsonify({ 'error': f'chat failed: {e}' }), 500
