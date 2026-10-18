"""Request / response models. These also feed the OpenAPI document that the
frontend's TypeScript types are generated from (scripts/gen_types.py)."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ auth
class Credentials(BaseModel):
    username: str
    password: str


class RegisterReq(Credentials):
    inviteCode: str


class PasswordReq(BaseModel):
    oldPassword: str
    newPassword: str


class User(BaseModel):
    id: int
    username: str
    role: Literal["admin", "user"]
    disabled: bool = False
    createdAt: Optional[str] = None
    lastLoginAt: Optional[str] = None


class MeOut(BaseModel):
    user: Optional[User] = None
    setupRequired: bool = False


class LoginOut(BaseModel):
    user: User


# ----------------------------------------------------------------- admin
class InviteReq(BaseModel):
    maxUses: int = 1
    expiresDays: Optional[int] = 7
    note: str = ""


class UserPatch(BaseModel):
    disabled: Optional[bool] = None


# -------------------------------------------------------------- practice
class GenerateReq(BaseModel):
    language: str = "en"
    level: str = "intermediate"
    mode: str = "questions"  # empty with a focus = use the mode suited to that skill
    topic: str = ""  # may be empty for a weak-skill drill (we pick one)
    count: int = 5
    focus: str = ""  # listening | pronunciation | fluency | grammar | vocabulary | content


class Turn(BaseModel):
    """One answer in a practice. Saved as you go (PUT /api/sessions/{id}/progress) and graded at the end."""
    id: str = ""  # stable id from the frontend (e.g. "q0", "q0-f1", "shadow-3")
    kind: str = "answer"  # answer | line | shadow | dictation | chat
    prompt: str = ""
    reference: str = ""
    freeResponse: bool = False
    answer: str = ""
    input: Literal["voice", "text"] = "text"
    durationSec: float = 0
    confidence: Optional[float] = None
    plays: int = 0
    textHidden: bool = False
    followUp: bool = False  # answer to an AI follow-up question
    audioUrl: str = ""  # saved recording (see /api/sessions/{id}/audio)
    shadowSync: bool = False  # shadowing while the original plays
    lagSec: Optional[float] = None
    durationRatio: Optional[float] = None
    pronScore: Optional[float] = None  # gateway pronunciation score (reading a script)
    pronNote: str = ""
    pronIssues: List[Dict[str, Any]] = Field(default_factory=list)
    voiceStartAt: Optional[float] = None


class QA(BaseModel):
    q: str = ""
    a: str = ""


class FollowUpReq(BaseModel):
    sessionId: str
    question: str
    answer: str
    history: List[QA] = Field(default_factory=list)


class ChatTurn(BaseModel):
    role: Literal["ai", "user"]
    text: str


class ChatReplyReq(BaseModel):
    sessionId: str
    history: List[ChatTurn] = Field(default_factory=list)
    summary: str = ""  # one-line summary of turns older than the recent window (returned by the last reply)


class SpokenText(BaseModel):
    text: str
    translation: str = ""  # always empty now: translations are fetched on demand


class ChatReplyOut(SpokenText):
    end: bool = False
    summary: str = ""


class EvaluateReq(BaseModel):
    sessionId: str
    turns: List[Turn] = Field(default_factory=list)


class ProgressReq(BaseModel):
    turns: List[Turn] = Field(default_factory=list)
    state: Optional[Dict[str, Any]] = None  # mode-specific UI state needed to resume (current index, chat log...)


class TranslateReq(BaseModel):
    texts: List[str] = Field(default_factory=list, max_length=40)
    language: str = "en"


class TranslateOut(BaseModel):
    translations: List[str]


class TTSReq(BaseModel):
    text: str
    language: str = "en"
    voiceIndex: int = 0
    rate: float = 1.0
    accent: str = "default"


class JobRef(BaseModel):
    jobId: str


class Job(BaseModel):
    id: str
    kind: Literal["generate", "evaluate", "notes", "course"]
    status: Literal["pending", "running", "done", "error"]
    result: Optional[Any] = None
    error: Optional[str] = None


class SessionOut(BaseModel):
    id: str
    createdAt: str
    content: Dict[str, Any]
    turns: List[Dict[str, Any]] = Field(default_factory=list)
    state: Optional[Dict[str, Any]] = None
    report: Optional[Dict[str, Any]] = None
    shareToken: Optional[str] = None


class SessionSummary(BaseModel):
    id: str
    language: Optional[str] = None
    level: Optional[str] = None
    mode: Optional[str] = None
    topic: Optional[str] = None
    title: Optional[str] = None
    overall: Optional[int] = None
    username: Optional[str] = None
    createdAt: str
    updatedAt: Optional[str] = None
    done: bool
    hasNotes: bool
    answered: int = 0


class TopicSummary(BaseModel):
    """Latest session for one language/level/mode/topic combination."""
    id: str
    language: Optional[str] = None
    level: Optional[str] = None
    mode: Optional[str] = None
    topic: Optional[str] = None
    title: Optional[str] = None
    overall: Optional[int] = None
    createdAt: str
    updatedAt: Optional[str] = None
    done: bool
    hasNotes: bool
    answered: int = 0
    attempts: int = 1


class PreviousSession(BaseModel):
    id: str
    createdAt: str
    title: Optional[str] = None
    overall: Optional[int] = None
    done: bool


class PreviousOut(BaseModel):
    previous: Optional[PreviousSession] = None


class StartedSession(BaseModel):
    id: str
    content: Dict[str, Any]


class ShareOut(BaseModel):
    token: Optional[str] = None
    url: Optional[str] = None


# ------------------------------------------------------------------ cards
class CardReq(BaseModel):
    language: str
    kind: Literal["word", "pattern", "sentence"] = "word"
    front: str
    reading: str = ""
    meaning: str = ""
    example: str = ""
    exampleTranslation: str = ""
    extra: str = ""
    sourceSession: str = ""


class ReviewReq(BaseModel):
    grade: Literal["again", "hard", "good", "easy"]
