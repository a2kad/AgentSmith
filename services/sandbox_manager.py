import asyncio
import uuid
from dataclasses import dataclass
from typing import AsyncGenerator


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    files_changed: dict[str, str]  # path -> content


class SandboxManager:
    def __init__(self, max_sandboxes: int = 5, timeout_sec: int = 120):
        self.pool: asyncio.Queue = asyncio.Queue(maxsize=max_sandboxes)
        self.timeout = timeout_sec
        self._active: dict[str, str] = {}  # task_id -> sandbox_id

    async def execute_code(
        self,
        code: str,
        language: str,
        task_id: str,
        working_dir_snapshot: dict[str, str],  # передаём только нужные файлы
    ) -> ExecutionResult:
        sandbox_id = f"sb-{uuid.uuid4().hex[:8]}"

        try:
            # 1. Spin up Firecracker microVM
            await self._start_sandbox(sandbox_id)

            # 2. Inject only necessary files (минимальный blast radius)
            await self._inject_files(sandbox_id, working_dir_snapshot)

            # 3. Execute with timeout + resource limits
            result = await asyncio.wait_for(
                self._run_in_sandbox(sandbox_id, code, language),
                timeout=self.timeout,
            )

            # 4. Extract changed files back
            result.files_changed = await self._extract_artifacts(sandbox_id)

            return result

        except asyncio.TimeoutError:
            return ExecutionResult("", "TIMEOUT", 124, self.timeout * 1000, {})

        finally:
            # 5. ВСЕГДА уничтожаем sandbox после выполнения
            await self._destroy_sandbox(sandbox_id)

    async def _destroy_sandbox(self, sandbox_id: str):
        """Полное уничтожение — никаких следов на хосте"""
        proc = await asyncio.create_subprocess_exec(
            "pkill",
            "-f",
            f"firecracker.*{sandbox_id}",
            stdout=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        await asyncio.create_subprocess_exec("ip", "link", "del", f"tap-{sandbox_id}")

    async def _start_sandbox(self, sandbox_id: str):
        raise NotImplementedError

    async def _inject_files(self, sandbox_id: str, working_dir_snapshot: dict[str, str]):
        raise NotImplementedError

    async def _run_in_sandbox(self, sandbox_id: str, code: str, language: str) -> ExecutionResult:
        raise NotImplementedError

    async def _extract_artifacts(self, sandbox_id: str) -> dict[str, str]:
        raise NotImplementedError
