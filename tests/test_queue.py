"""Tests for TTS queue manager."""

import pytest
from microtherapy.queue import TTSQueueManager


class TestTTSQueueManager:
    def test_create_queue(self):
        mgr = TTSQueueManager()
        qid = mgr.create_queue("default")
        assert len(qid) == 12
        assert qid in mgr._queues

    def test_add_text_initial(self):
        mgr = TTSQueueManager()
        qid = mgr.create_queue("default")
        added = mgr.add_text(qid, "Hello world")
        assert added == 11
        assert mgr._queues[qid].full_text == "Hello world"

    def test_add_text_replacement(self):
        """When text starts with existing, it replaces with fuller version."""
        mgr = TTSQueueManager()
        qid = mgr.create_queue("default")
        mgr.add_text(qid, "Hello")
        added = mgr.add_text(qid, "Hello world")
        assert added == 6
        assert mgr._queues[qid].full_text == "Hello world"

    def test_add_text_append(self):
        """When text doesn't start with existing, it appends."""
        mgr = TTSQueueManager()
        qid = mgr.create_queue("default")
        mgr.add_text(qid, "Hello")
        added = mgr.add_text(qid, " world")
        assert added == 6
        assert mgr._queues[qid].full_text == "Hello world"

    def test_get_new_chunks_consumed(self):
        mgr = TTSQueueManager()
        qid = mgr.create_queue("default")
        mgr._queues[qid].audio_chunks = [b"chunk1"]
        chunks = mgr.get_new_chunks(qid)
        assert len(chunks) == 1
        # Second call returns empty
        chunks = mgr.get_new_chunks(qid)
        assert len(chunks) == 0

    def test_end_queue(self):
        mgr = TTSQueueManager()
        qid = mgr.create_queue("default")
        assert not mgr.is_done(qid)
        mgr.end_queue(qid)
        assert mgr.is_done(qid)
