class SentenceSelector:
    """Compares two sentence candidates and returns the better one."""

    def is_better(self, new: dict, existing: dict) -> bool:
        raise NotImplementedError


class AudioThenShortestSelector(SentenceSelector):
    def is_better(self, new, existing):
        if new["has_audio"] and not existing["has_audio"]:
            return True
        if new["has_audio"] == existing["has_audio"] and new["length"] < existing["length"]:
            return True
        return False


class TranscriptionThenShortestSelector(SentenceSelector):
    """Prefers transcription with username, then without, then no transcription. Tiebreaks on shorter sentence."""

    def is_better(self, new, existing):
        if new["t_rank"] < existing["t_rank"]:
            return True
        if new["t_rank"] == existing["t_rank"] and new["length"] < existing["length"]:
            return True
        return False