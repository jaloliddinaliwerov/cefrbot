from aiogram.fsm.state import State, StatesGroup

class ReadingState(StatesGroup):
    answering = State()  # question_id

class ListeningState(StatesGroup):
    answering = State()  # question_id

class WritingState(StatesGroup):
    submitting = State()  # task_id

class SpeakingState(StatesGroup):
    submitting = State()  # task_id

class MockState(StatesGroup):
    answering_reading = State()  # mock_id, question_index
    answering_listening = State()  # mock_id, question_index
    submitting_writing = State()  # mock_id, task_id
    submitting_speaking = State()  # mock_id, task_id
