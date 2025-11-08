import os
import re
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

try:
    import nltk
    from nltk.tokenize import sent_tokenize
    NLTK_AVAILABLE = True
    logger.info("NLTK loaded successfully")
except ImportError:
    NLTK_AVAILABLE = False

if NLTK_AVAILABLE:
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        try:
            nltk.download('punkt', quiet=True)
        except Exception:
            NLTK_AVAILABLE = False

def generate_meeting_minutes(full_text):
    cleaned_text = full_text.strip()
    
    if not cleaned_text:
        return {
            "summary": "No transcript text provided.",
            "decisions": "No transcript text provided.", 
            "action_items": "No transcript text provided.",
            "deadlines": "No transcript text provided."
        }

    logger.info(f"Processing transcript: {len(cleaned_text)} chars")
    
    summary = generate_summary(cleaned_text)
    decisions = extract_decisions(cleaned_text)
    action_items = extract_action_items(cleaned_text)
    deadlines = extract_deadlines(cleaned_text)
    
    return {
        "summary": format_text(summary),
        "decisions": format_list(decisions, "decision"),
        "action_items": format_list(action_items, "action item"),
        "deadlines": format_list(deadlines, "deadline")
    }

def generate_summary(text):
    if not text.strip():
        return "No summary available."
    
    sentences = sent_tokenize(text) if NLTK_AVAILABLE else re.split(r'(?<=[.!?])\s+', text)
    cleaned_sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    
    if not cleaned_sentences:
        return text[:300] + "..." if len(text) > 300 else text
    
    scored_sentences = []
    for idx, sentence in enumerate(cleaned_sentences):
        score = calculate_sentence_importance(sentence, idx, len(cleaned_sentences))
        scored_sentences.append((score, sentence))
    
    scored_sentences.sort(reverse=True, key=lambda x: x[0])
    num_sentences = min(max(3, len(cleaned_sentences) // 10), 8)
    top_sentences = [s[1] for s in scored_sentences[:num_sentences]]
    
    ordered_summary_sentences = [s for s in cleaned_sentences if s in top_sentences]
    summary = " ".join(ordered_summary_sentences)
    
    return summary + '.' if summary and not summary.endswith(('.', '!', '?')) else summary

def calculate_sentence_importance(sentence, position, total_sentences):
    score = 0.0
    sentence_lower = sentence.lower()
    
    important_keywords = [
        'decided', 'agreed', 'concluded', 'will', 'should', 'must',
        'important', 'critical', 'key', 'main', 'primary',
        'action', 'deadline', 'by', 'before', 'need to', 'have to',
        'summary', 'conclusion', 'result', 'outcome',
        'goal', 'objective', 'priority', 'focus'
    ]
    
    for keyword in important_keywords:
        if keyword in sentence_lower:
            score += 1.0
    
    if position < 3:
        score += 2.0
    if position >= total_sentences - 3:
        score += 1.5
    
    word_count = len(sentence.split())
    if 10 <= word_count <= 30:
        score += 1.0
    elif word_count < 5:
        score -= 2.0
    
    if re.search(r'\d', sentence):
        score += 0.5
    
    return score

def extract_decisions(text):
    decisions = []
    sentences = sent_tokenize(text) if NLTK_AVAILABLE else re.split(r'(?<=[.!?])\s+', text)
    
    decision_patterns = [
        r'\b(decided|agreed|concluded|determined|resolved|settled)\b',
        r'\b(we will|we\'ll|let\'s|we should|we must)\b',
        r'\b(approved|accepted|confirmed|finalized|committed to)\b',
        r'\b(going with|moving forward with|proceeding with)\b',
        r'\b(final decision|unanimous|consensus|voted to)\b',
        r'\b(decision:|conclusion:)\s*',
        r'\b(plan to|going to|will be|shall)\b',
        r'\b(selected|chose|picked|opted for)\b',
        r'\b(scheduled|arranged|organized)\b',
        r'\b(changed|updated|modified)\b',
        r'\b(adopted|implemented|established)\b',
    ]
    
    decision_indicators = [
        'decide', 'agree', 'conclude', 'determine', 'resolve', 'settle',
        'will', 'shall', 'must', 'should', 'plan to', 'going to',
        'approved', 'accepted', 'confirmed', 'finalized', 'committed',
        'selected', 'chose', 'picked', 'opted', 'scheduled',
        'changed', 'updated', 'modified', 'adopted', 'implemented',
        'established', 'consensus', 'majority', 'unanimous'
    ]
    
    for sentence in sentences:
        for pattern in decision_patterns:
            if re.search(pattern, sentence.lower()):
                cleaned = clean_text(sentence)
                if cleaned and len(cleaned.split()) >= 5:
                    decisions.append(cleaned)
                    break
        
        else:
            if any(indicator in sentence.lower() for indicator in decision_indicators):
                cleaned = clean_text(sentence)
                if cleaned and len(cleaned.split()) >= 5:
                    decisions.append(cleaned)
    
    return remove_duplicates(decisions)[:10]

def extract_action_items(text):
    action_items = []
    sentences = sent_tokenize(text) if NLTK_AVAILABLE else re.split(r'(?<=[.!?])\s+', text)
    
    action_patterns = [
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:will|should|needs? to|has to|must|is going to)\s+([^.!?]{10,})',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:is|will be)\s+(?:responsible for|in charge of|handling)\s+([^.!?]{10,})',
        r'(?:action item|task|todo|to-do|assignment):\s*([^.!?]{10,})',
        r'(?:please|can you|could you|would you)\s+([^.!?]{10,})',
        r'\b(?:we|someone|somebody)\s+(?:need to|have to|must|should)\s+([^.!?]{10,})',
    ]
    
    for sentence in sentences:
        for pattern in action_patterns:
            matches = re.finditer(pattern, sentence, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) >= 2:
                    action_item = f"{match.group(1).strip()}: {match.group(2).strip()}"
                elif len(match.groups()) == 1:
                    action_item = match.group(1).strip()
                else:
                    continue
                
                action_clean = clean_text(action_item)
                if action_clean and len(action_clean.split()) >= 3:
                    action_items.append(action_clean)
    
    return remove_duplicates(action_items)[:15]

def extract_deadlines(text):
    deadlines = []
    sentences = sent_tokenize(text) if NLTK_AVAILABLE else re.split(r'(?<=[.!?])\s+', text)
    
    # Enhanced deadline patterns with specific dates and times
    deadline_patterns = [
        # Original patterns
        r'(?:by|before|until|no later than|due)\s+([A-Z][a-z]+day(?:\s+\w+)*|(?:the\s+)?\d{1,2}(?:st|nd|rd|th)?(?:\s+of)?\s+\w+|\d{1,2}/\d{1,2})',
        r'(?:deadline|due date)(?:\s+is)?:?\s+([\w\s,]+)',
        r'(?:complete|finish|submit|deliver|send)\s+(?:by|before)\s+([\w\s,]+)',
        r'\b(tomorrow|today|tonight|this week|next week|this month|next month|end of (?:week|month|quarter|year))\b',
        r'(?:in|within)\s+(\d+\s+(?:days?|weeks?|months?))',
        
        # NEW PATTERNS FOR SPECIFIC DATES
        # Date formats: DD/MM/YYYY, DD-MM-YYYY, MM/DD/YYYY
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        # Date formats: Month DD, YYYY (e.g., May 18, 2025)
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:st|nd|rd|th)?,? \d{4}\b',
        # Date formats: DD Month YYYY (e.g., 18 May 2025)
        r'\b\d{1,2}(?:st|nd|rd|th)? (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}\b',
        
        # NEW PATTERNS FOR TIMES
        # Time formats: HH:MM (e.g., 5:00, 17:30)
        r'\b\d{1,2}:\d{2}\b',
        # Time formats: HH:MM AM/PM (e.g., 5:00 PM)
        r'\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)\b',
        
        # COMBINED DATE AND TIME
        # Date and time together (e.g., 18/5/2025 at 5:00)
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s+(?:at\s+)?\d{1,2}:\d{2}(?:\s*(?:AM|PM|am|pm))?\b',
        # Month DD, YYYY at HH:MM (e.g., May 18, 2025 at 5:00 PM)
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:st|nd|rd|th)?,? \d{4}\s+(?:at\s+)?\d{1,2}:\d{2}(?:\s*(?:AM|PM|am|pm))?\b',
    ]
    
    # Expanded time indicators
    time_indicators = [
        'deadline', 'due', 'by', 'before', 'until', 'asap', 'urgent',
        'priority', 'immediately', 'soon', 'quickly', 'tomorrow', 'today',
        'week', 'month', 'quarter', 'year',
        # NEW INDICATORS
        'at', 'on', 'date', 'time', 'schedule', 'appointment'
    ]
    
    for sentence in sentences:
        if any(indicator in sentence.lower() for indicator in time_indicators):
            for pattern in deadline_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    cleaned = clean_text(sentence)
                    if cleaned and len(cleaned.split()) >= 3:
                        deadlines.append(cleaned)
                        break
    
    return remove_duplicates(deadlines)[:10]

def clean_text(text):
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'^\[?\d+:\d+:\d+\]?\s*', '', text)
    text = re.sub(r'^SPEAKER_\d+:\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^[A-Z\s]+:\s*', '', text)
    text = re.sub(r'^\[\d+\.\d+-\d+\.\d+\]\s*', '', text)
    
    if text:
        text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
    
    return text + '.' if text and not re.search(r'[.!?]$', text) else text

def remove_duplicates(items):
    seen = set()
    unique_items = []
    for item in items:
        key = item.lower().strip()[:50]
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    return unique_items

def format_text(text):
    if not text or text.strip() in ["No summary available.", "No transcript text provided."]:
        return "No summary available."
    
    text = re.sub(r'\s+', ' ', text).strip()
    return text + '.' if text and not text.endswith(('.', '!', '?')) else text

def format_list(items, item_type):
    if not items:
        return f"No explicit {item_type}s identified."
    
    return "\n".join(f"• {item}" for item in items)