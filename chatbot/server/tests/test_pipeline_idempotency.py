import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import chat_pipeline  # noqa: E402
from chat_pipeline import ChatPipelineRequest, ChatPipelineResponse, process_chat_pipeline  # noqa: E402


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def delete(self, key):
        self.values.pop(key, None)

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    async def ltrim(self, key, start, end):
        values = self.lists.get(key, [])
        self.lists[key] = values[start:] if start < 0 else values[start:end + 1]

    async def expire(self, key, seconds):
        return None

    async def eval(self, script, count, key, token):
        if self.values.get(key) == token:
            await self.delete(key)
            return 1
        return 0


class PipelineIdempotencyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        chat_pipeline._local_session_cache.clear()
        chat_pipeline._local_customer_cache.clear()

    async def test_same_message_id_executes_and_persists_once(self):
        redis_client = FakeRedis()
        response = ChatPipelineResponse(
            answer="Hotline ZeO 1900 5307",
            intent="company_contact_information",
            confidence="high",
            score=1.0,
            brand="ZEO",
        )
        execute_once = AsyncMock(return_value=response)
        request = ChatPipelineRequest(
            brand="zeo",
            sender_id="sender-1",
            text="Cho mình xin hotline",
            message_id="mid-1",
        )

        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=redis_client)), \
                patch("chat_pipeline._process_chat_pipeline_once", execute_once):
            first = await process_chat_pipeline(request)
            second = await process_chat_pipeline(request)

        self.assertFalse(first.duplicate)
        self.assertEqual(first.idempotency_status, "processed")
        self.assertTrue(second.duplicate)
        self.assertEqual(second.idempotency_status, "cached")
        execute_once.assert_awaited_once()
        self.assertEqual(len(redis_client.lists["zeo:history:messenger:sender-1"]), 1)

    async def test_same_text_with_different_message_ids_executes_twice(self):
        redis_client = FakeRedis()
        execute_once = AsyncMock(side_effect=[
            ChatPipelineResponse(
                answer="Hotline ZeO 1900 5307", intent="company_contact_information",
                confidence="high", score=1.0, brand="ZEO",
            ),
            ChatPipelineResponse(
                answer="Hotline ZeO 1900 5307", intent="company_contact_information",
                confidence="high", score=1.0, brand="ZEO",
            ),
        ])
        first_request = ChatPipelineRequest(
            brand="zeo", sender_id="sender-repeat", text="Cho mình xin hotline", message_id="mid-a",
        )
        second_request = ChatPipelineRequest(
            brand="zeo", sender_id="sender-repeat", text="Cho mình xin hotline", message_id="mid-b",
        )

        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=redis_client)), \
                patch("chat_pipeline._process_chat_pipeline_once", execute_once):
            first = await process_chat_pipeline(first_request)
            second = await process_chat_pipeline(second_request)

        self.assertFalse(first.duplicate)
        self.assertFalse(second.duplicate)
        self.assertEqual(execute_once.await_count, 2)
        self.assertEqual(len(redis_client.lists["zeo:history:messenger:sender-repeat"]), 2)

    async def test_same_message_id_is_isolated_by_brand_and_sender_state_by_both(self):
        redis_client = FakeRedis()

        async def execute(request):
            return ChatPipelineResponse(
                answer=f"{request.brand}:{request.sender_id}",
                intent="greeting",
                confidence="high",
                score=1.0,
                brand=request.brand.upper(),
            )

        requests = (
            ChatPipelineRequest(brand="zeo", sender_id="same-sender", text="Alo", message_id="same-mid"),
            ChatPipelineRequest(brand="cfc", sender_id="same-sender", text="Alo", message_id="same-mid"),
            ChatPipelineRequest(brand="zeo", sender_id="sender-a", text="Alo", message_id="mid-a"),
            ChatPipelineRequest(brand="zeo", sender_id="sender-b", text="Alo", message_id="mid-b"),
        )

        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=redis_client)), \
                patch("chat_pipeline._process_chat_pipeline_once", new=AsyncMock(side_effect=execute)) as execute_once:
            responses = [await process_chat_pipeline(request) for request in requests]

        self.assertEqual(execute_once.await_count, 4)
        self.assertTrue(all(not response.duplicate for response in responses))
        for request in requests:
            key = f"{request.brand}:session:messenger:{request.sender_id}"
            self.assertEqual(chat_pipeline._local_session_cache[key]["sender_id"], request.sender_id)

    async def test_in_flight_duplicate_is_not_executed(self):
        redis_client = FakeRedis()
        request = ChatPipelineRequest(
            brand="zeo",
            sender_id="sender-2",
            text="Alo",
            message_id="mid-busy",
        )
        from message_idempotency import _keys

        lease_key, _ = _keys("zeo", "mid-busy")
        redis_client.values[lease_key] = "another-worker"
        execute_once = AsyncMock()
        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=redis_client)), \
                patch("chat_pipeline._process_chat_pipeline_once", execute_once):
            result = await process_chat_pipeline(request)

        self.assertTrue(result.duplicate)
        self.assertEqual(result.idempotency_status, "in_flight")
        execute_once.assert_not_awaited()

    async def test_unremembered_fast_path_is_finalized(self):
        redis_client = FakeRedis()
        execute_once = AsyncMock(return_value=ChatPipelineResponse(
            answer="Dạ ZeO chào bạn",
            intent="greeting",
            confidence="high",
            score=1.0,
            brand="ZEO",
        ))
        request = ChatPipelineRequest(brand="zeo", sender_id="sender-3", text="Alo")
        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=redis_client)), \
                patch("chat_pipeline._process_chat_pipeline_once", execute_once):
            await process_chat_pipeline(request)

        session = chat_pipeline._local_session_cache["zeo:session:messenger:sender-3"]
        self.assertEqual(session["last_intent"], "greeting")
        self.assertEqual(session["conversation_state"]["recent_turns"][-1]["user"], "Alo")
        self.assertEqual(session["revision"], 1)
        self.assertNotIn("zeo:sender-3", chat_pipeline._sender_locks)
        self.assertNotIn("zeo:sender-3", chat_pipeline._sender_lock_users)


if __name__ == "__main__":
    unittest.main()
