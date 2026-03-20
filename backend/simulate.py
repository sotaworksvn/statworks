"""POST /simulate — Scenario Simulation endpoint (F-03)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.engines.simulation import build_graph, dfs_propagate
from backend.models import ImpactResult, SimulateRequest, SimulationResponse
from backend.store import get_entry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/simulate", response_model=SimulationResponse)
async def simulate(body: SimulateRequest) -> SimulationResponse:
    """Run a single-variable delta propagation simulation."""

    try:
        # 1. Lookup file_id
        entry = await get_entry(body.file_id)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail="file_id not found. Please upload a dataset first.",
            )

        # 2. Check coefficient_cache
        if entry.coefficient_cache is None:
            raise HTTPException(
                status_code=409,
                detail="Run /analyze before /simulate.",
            )

        # 3. Validate variable
        valid_vars = list(entry.coefficient_cache.keys())
        if body.variable not in valid_vars:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": f"Variable '{body.variable}' not found.",
                    "valid_variables": valid_vars,
                },
            )

        # 4. Build graph and propagate
        graph = build_graph(entry.coefficient_cache)
        raw_impacts = dfs_propagate(graph, body.variable, body.delta)

        # 5. Build response
        impacts = [
            ImpactResult(
                variable=var,
                delta_pct=round(delta * 100, 1),  # convert fraction → percentage
            )
            for var, delta in raw_impacts.items()
            if var != body.variable
        ]

        # Sort by absolute impact descending
        impacts.sort(key=lambda x: abs(x.delta_pct), reverse=True)

        return SimulationResponse(
            variable=body.variable,
            delta=body.delta,
            impacts=impacts,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in /simulate")
        raise HTTPException(
            status_code=500,
            detail="Unexpected error. Please try again.",
        ) from exc
