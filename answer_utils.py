"""
Universal answer parser for CEFR bot.
Handles all common formats users might write their answers in.
"""
import re


def parse_answers_universal(text: str) -> dict:
    """
    Parse user answers from any format. Returns {question_number: answer_string}.
    
    Supported formats:
      "1-A, 2-B, 3-C"          -> {1: 'A', 2: 'B', 3: 'C'}
      "1.A 2.B 3.C"             -> {1: 'A', 2: 'B', 3: 'C'}
      "1: A\n2: B\n3: C"        -> {1: 'A', 2: 'B', 3: 'C'}
      "1 A, 2 B, 3 C"           -> {1: 'A', 2: 'B', 3: 'C'}
      "1A 2B 3C"                -> {1: 'A', 2: 'B', 3: 'C'}
      "A B C D"                 -> {1: 'A', 2: 'B', 3: 'C', 4: 'D'}  (positional)
      "1) apple\n2) orange"     -> {1: 'apple', 2: 'orange'}
      "1-Apple 2-Orange 3-Banana" -> {1: 'Apple', 2: 'Orange', 3: 'Banana'}
    """
    text = text.strip()
    answers = {}

    # Strategy 1: Standard "N[sep]answer" patterns where sep is -, ., :, ), space
    # This covers "1-A", "1.A", "1: A", "1) A", "1 A"
    # Matches: digit(s) + optional separator + answer word
    pattern_with_sep = re.compile(
        r'(?:^|[\n,;|\s])(\d{1,3})\s*[-.:)]\s*([^\n,;|]+?)(?=\s*(?:\d{1,3}\s*[-.:)]|$|[\n,;|]))',
        re.MULTILINE
    )
    matches = pattern_with_sep.findall(text)
    if matches:
        for q_str, ans in matches:
            q = int(q_str)
            a = ans.strip().rstrip('.,; ')
            if a:
                answers[q] = a
        if len(answers) >= 1:
            return answers

    # Strategy 2: Simple "N-answer" or "N. answer" without requiring delimiter between pairs
    pattern_simple = re.compile(r'(\d{1,3})\s*[-.:)]\s*(\S+(?:\s+\S+)*?)(?=\s+\d{1,3}\s*[-.:)]|$)', re.MULTILINE)
    matches2 = pattern_simple.findall(text)
    if matches2:
        for q_str, ans in matches2:
            q = int(q_str)
            a = ans.strip().rstrip('.,; ')
            if a:
                answers[q] = a
        if len(answers) >= 1:
            return answers

    # Strategy 3: "NAnswer" glued together like "1A 2B 3C" or "1A,2B,3C"
    pattern_glued = re.compile(r'(\d{1,3})([A-Za-z][a-zA-Z]*)')
    matches3 = pattern_glued.findall(text)
    if matches3:
        for q_str, ans in matches3:
            q = int(q_str)
            if 1 <= q <= 200:  # sanity check
                answers[q] = ans.strip()
        if len(answers) >= 1:
            return answers

    # Strategy 4: Positional — if user just writes "A B C D" or "A,B,C,D" without numbers
    # Only use if no numbers found at all
    if not re.search(r'\d', text):
        tokens = re.split(r'[\s,;\n|]+', text.strip())
        tokens = [t.strip() for t in tokens if t.strip()]
        if tokens:
            for idx, tok in enumerate(tokens, 1):
                answers[idx] = tok
            return answers

    return answers


def check_answers(user_answers: dict, questions_list: list) -> tuple:
    """
    Compare user answers against correct answers.
    Returns (correct_count, result_details, wrong_answers_dict)
    
    questions_list items: {"id": N, "q": "...", "options": [...], "answer": "A"}
    """
    correct_count = 0
    result_details = []
    wrong_answers = {}

    def clean(s: str) -> str:
        """Normalize for comparison: lowercase, strip punctuation/spaces."""
        s = s.strip().lower()
        s = re.sub(r'[^\w]', '', s)
        return s

    for idx, q_item in enumerate(questions_list, 1):
        q_id = q_item.get("id", idx)
        correct_raw = str(q_item.get("answer", "")).strip()
        has_opts = len(q_item.get('options', [])) > 0

        # Try matching by both the stored id and sequential index
        user_ans = str(
            user_answers.get(q_id) or
            user_answers.get(idx) or
            ""
        ).strip()

        if not correct_raw:
            # No correct answer stored — mark as not checked
            result_details.append(f"⚪ {q_id}-savol: Javob kaliti yo'q")
            continue

        # For multiple-choice: compare only the letter part
        if has_opts:
            correct_letter = correct_raw.split(":")[0].strip().upper()
            user_letter = user_ans.split(":")[0].strip().upper()
            is_correct = (user_letter == correct_letter) and bool(user_letter)
            show_correct = correct_letter
        else:
            # Free-text: compare cleaned strings
            is_correct = bool(user_ans) and (clean(user_ans) == clean(correct_raw))
            show_correct = correct_raw

        if is_correct:
            correct_count += 1
            result_details.append(f"✅ {q_id}-savol: To'g'ri")
        else:
            wrong_answers[str(q_id)] = user_ans
            disp_ans = user_ans if user_ans else "Javob berilmadi"
            result_details.append(
                f"❌ {q_id}-savol: Noto'g'ri (Siz: {disp_ans} | To'g'ri: {show_correct})"
            )

    return correct_count, result_details, wrong_answers


async def send_result_messages(message, result_details: list, header: str = ""):
    """
    Send result details, splitting into multiple messages if needed
    to avoid Telegram's 4096-char limit.
    """
    MAX_LEN = 3800

    if header:
        lines = [header, ""] + result_details
    else:
        lines = result_details

    chunk = ""
    for line in lines:
        candidate = chunk + line + "\n"
        if len(candidate) > MAX_LEN:
            if chunk:
                await message.answer(chunk.strip())
            chunk = line + "\n"
        else:
            chunk = candidate

    if chunk.strip():
        await message.answer(chunk.strip())
