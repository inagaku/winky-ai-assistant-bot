
response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a parameter extraction assistant.\n"
                            "Extract only the predefined parameters from the user input and return them as a valid JSON object.\n"
                            "Include ONLY fields that are explicitly mentioned or clearly implied.\n"
                            "Do NOT invent values, do NOT guess times, and do NOT include null fields.\n"
                            "If no parameters apply, return {}.\n"
                            "Return JSON only, with no extra text."
                        ),
                    },
                    {"role": "user", "content": """
                    Extract parameters from this user input for a {action_type.value} action.

User input: "{user_input}"

Expected parameters:
{
        "required": ["title", "description"],
        "optional": ["remind_at_explicit", "event_time", "lead_time"],
        "schema": {
            "title": "Short, imperative summary of the reminder suitable as a notification title (string, required). Example: 'Call John', 'Submit tax form'",
            "description": "Full natural-language description of what needs to be done, including context or details not suitable for the title (string, required)",
            "remind_at_explicit": "Absolute notification time. Use when the user specifies a direct reminder time independent of an event (e.g., 'remind me at 4pm', 'set a reminder for tomorrow morning', 'ping me tonight'). Natural language time. Do not set if the time clearly refers to when an event happens rather than when to be notified.",
            "event_time": "When the actual event or action occurs (not the notification). Use if the user describes something happening at a time (e.g., 'the meeting is at 3pm', 'my flight departs tomorrow at 9', 'I need to do it by the end of month'). Natural language time.",
            "lead_time": "Relative offset before event_time indicating when to notify. Use only if the user specifies a relative time (e.g., '30 minutes before', '2 hours earlier', 'the day before'). Store as a duration string or normalized minutes. If lead_time is set, event_time MUST also be set. Do not infer event_time.",
        },
        "additional_rules": "If a relative time is mentioned and no event_time is present, it MUST be interpreted as remind_at_explicit.
    }
                    """},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )