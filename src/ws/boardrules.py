"""Regras do quadro: o que o código prova de cada card vira movimento, retenção ou aviso."""

from dataclasses import asdict
from datetime import date

from ws.boardconfig import BoardConfig
from ws.codeposition import Position
from ws.taskmodel import RUNG, STATUS_AT_RUNG, Status, Task
from ws.workdays import previous_workday


def _epic_keys(tasks: list[Task]) -> set[str]:
    return {task.epic_key for task in tasks if task.epic_key}


def _holding_json(position: Position) -> dict | None:
    if position.holding is None:
        return None
    holding = asdict(position.holding)
    if holding["reached"] is None:
        holding["tag"] = None
    return holding


def plan_moves(
    tasks: list[Task], positions: dict[str, Position], cfg: BoardConfig, today: date
) -> dict:
    epics = _epic_keys(tasks)
    moves: list[dict] = []
    held: list[dict] = []
    limited: list[dict] = []
    to_confirm: list[dict] = []
    cutoff = previous_workday(today)
    for task in tasks:
        if task.status not in RUNG or task.status == Status.DONE:
            continue
        if task.is_epic or task.key in epics:
            continue
        position = positions.get(task.key)
        target = STATUS_AT_RUNG.get(position.rung) if position else None
        moved = position is not None and target is not None and position.rung > RUNG[task.status]
        if not moved and task.status == Status.VALIDATION and task.updated.date() <= cutoff:
            to_confirm.append(
                {"key": task.key, "title": task.title, "since": task.updated.date().isoformat()}
            )
        if position is None:
            continue
        if moved:
            moves.append(
                {
                    "key": task.key,
                    "title": task.title,
                    "from": task.status.value,
                    "to": target.value,
                    "to_name": cfg.statuses[target],
                    "environment": position.environment,
                    "stale": position.stale,
                }
            )
        elif position.holding is not None:
            held.append(
                {
                    "key": task.key,
                    "title": task.title,
                    "status": task.status.value,
                    "holding": _holding_json(position),
                }
            )
        if position.limited and target is not None:
            limited.append(
                {
                    "key": task.key,
                    "title": task.title,
                    "status": task.status.value,
                    "proves": target.value,
                    "repos": list(position.repos),
                }
            )
    return {"moves": moves, "held": held, "limited": limited, "to_confirm": to_confirm}
