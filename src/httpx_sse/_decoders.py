from typing import AsyncIterator, Iterator, List, Optional

import httpx

from ._models import ServerSentEvent


def iter_sse(response: httpx.Response) -> Iterator[ServerSentEvent]:
    decoder = _SSEDecoder()

    for line in response.iter_lines():
        sse = decoder.decode(line)
        if sse is not None:
            yield sse


async def aiter_sse(response: httpx.Response) -> AsyncIterator[ServerSentEvent]:
    decoder = _SSEDecoder()

    async for line in response.aiter_lines():
        sse = decoder.decode(line)
        if sse is not None:
            yield sse


class _SSEDecoder:
    def __init__(self) -> None:
        self._event = ""
        self._data: List[str] = []
        self._last_event_id = ""
        self._retry: Optional[int] = None

    def decode(self, line: str) -> Optional[ServerSentEvent]:
        # See: https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation  # noqa: E501

        line = line[:-1]  # Drop trailing '\n'

        if not line:
            if (
                not self._event
                and not self._data
                and not self._last_event_id
                and self._retry is None
            ):
                return None

            sse = ServerSentEvent(
                event=self._event or "message",
                data="\n".join(self._data),
                id=self._last_event_id,
                retry=self._retry,
            )

            # NOTE: as per the SSE spec, do not reset last_event_id does not get reset.
            self._event = ""
            self._data = []
            self._retry = None

            return sse

        if line.startswith(":"):
            return None

        fieldname, _, value = line.partition(":")

        if value.startswith(" "):
            value = value[1:]

        if fieldname == "event":
            self._event = value
        elif fieldname == "data":
            self._data.append(value)
        elif fieldname == "id":
            if "\0" in value:
                pass
            else:
                self._last_event_id = value
        elif fieldname == "retry":
            try:
                self._retry = int(value)
            except (TypeError, ValueError):
                pass
        else:
            pass  # Field is ignored.

        return None
