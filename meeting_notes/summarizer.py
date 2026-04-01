from typing import List, Optional

from openai import OpenAI, APIConnectionError, APIStatusError
from rich.console import Console

SYSTEM_PROMPT = """You are a meeting assistant. Extract the key information from meeting transcripts.
Be concise. Format your response in two sections:
1. **Summary** (2-4 sentences describing what was discussed)
2. **Action Items** (bulleted list of concrete next steps; include owner if mentioned)
If the transcript is too short or unclear, say so briefly."""


class Summarizer:
    def __init__(self, base_url: str):
        self._base_url = base_url
        self._client: Optional[OpenAI] = None

    def check_connection(self) -> Optional[str]:
        """Returns an error message string if LM Studio is unreachable, else None."""
        try:
            client = self._get_client()
            models = client.models.list()
            if not models.data:
                return "LM Studio is running but no model is loaded. Load a model before running."
            return None
        except APIConnectionError:
            return f"Cannot reach LM Studio at {self._base_url}. Is LM Studio running?"
        except Exception as e:
            return f"LM Studio check failed: {e}"

    def summarize(self, transcript_lines: List[str], console: Console) -> Optional[str]:
        """
        Stream a summary to the console. Returns the full summary text,
        or None if LM Studio is unreachable (raw transcript already saved by caller).
        """
        if not transcript_lines:
            console.print("[yellow]No transcript to summarize.[/yellow]")
            return None

        transcript_text = "\n".join(transcript_lines)

        try:
            client = self._get_client()
            console.print("\n[bold cyan]Generating summary...[/bold cyan]\n")

            stream = client.chat.completions.create(
                model="local-model",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": transcript_text},
                ],
                temperature=0.3,
                max_tokens=1024,
                stream=True,
            )

            full_response = []
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    console.print(delta, end="")
                    full_response.append(delta)
            console.print()  # final newline
            return "".join(full_response)

        except APIConnectionError:
            console.print(
                f"[red]Cannot reach LM Studio at {self._base_url}.[/red]\n"
                "[yellow]Raw transcript saved. Summary skipped.[/yellow]"
            )
            return None
        except APIStatusError as e:
            if e.status_code in (400, 503):
                console.print(
                    "[red]LM Studio returned an error — is a model loaded?[/red]\n"
                    f"[dim]{e.message}[/dim]\n"
                    "[yellow]Raw transcript saved. Summary skipped.[/yellow]"
                )
            else:
                console.print(f"[red]LM Studio error {e.status_code}: {e.message}[/red]")
            return None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(base_url=self._base_url, api_key="lm-studio")
        return self._client
