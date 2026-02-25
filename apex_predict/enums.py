from enum import Enum


class SessionState(str, Enum):
    SCHEDULED = "SCHEDULED"
    OPEN = "OPEN"
    LOCKED = "LOCKED"
    SCORING = "SCORING"
    FINALIZED = "FINALIZED"


class SessionType(str, Enum):
    FP1 = "FP1"
    FP2 = "FP2"
    FP3 = "FP3"
    SPRINT_QUALIFYING = "SPRINT_QUALIFYING"
    SPRINT = "SPRINT"
    QUALIFYING = "QUALIFYING"
    RACE = "RACE"


class QuestionType(str, Enum):
    POLE = "POLE"
    WINNER = "WINNER"
    TOP5 = "TOP5"
    DNF = "DNF"
    FASTEST_LAP = "FASTEST_LAP"
    SAFETY_CAR = "SAFETY_CAR"
    MIDFIELD_CONSTRUCTOR = "MIDFIELD_CONSTRUCTOR"
    FIRST_PIT_STOP_TEAM = "FIRST_PIT_STOP_TEAM"
    FIRST_SAFETY_CAR_LAP = "FIRST_SAFETY_CAR_LAP"


class LeagueVisibility(str, Enum):
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"


class JoinPolicy(str, Enum):
    INVITE_ONLY = "INVITE_ONLY"
    OPEN = "OPEN"


class ModerationState(str, Enum):
    ACTIVE = "ACTIVE"
    REVIEW = "REVIEW"
    SUSPENDED = "SUSPENDED"


class MemberRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class ReportStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class LeaderboardScope(str, Enum):
    GLOBAL = "GLOBAL"
    LEAGUE = "LEAGUE"
