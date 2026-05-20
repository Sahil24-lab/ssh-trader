import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import { execFile } from "node:child_process";
import { buildDashboardPayload, DashboardCsvPaths, ROOT_DIR } from "@/lib/dashboard/csv";
import { NextRequest, NextResponse } from "next/server";

const execFileAsync = promisify(execFile);

export const dynamic = "force-dynamic";

type RunRequest = {
  csvPath?: string;
  csv4hPath?: string;
  timeframe?: string;
  fillMissing?: boolean;
  initialNav?: number;
  aggressiveness?: number;
  leverageCap?: number;
  venueCapFrac?: number;
  maxDrawdown?: number;
  liquidationBuffer?: number;
  targetDirVol?: number;
  takerFeeBps?: number;
  slippageBpsAt1xNav?: number;
  orderLatencyBars?: number;
  fillRangePosition?: number;
  fillTimeFraction?: number;
  directionalStopLossPct?: number;
  directionalTakeProfitPct?: number;
  directionalMaxHoldBars?: number;
  carryRebalanceThresholdPct?: number;
  carryEnabled?: boolean;
};

function num(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function str(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : fallback;
}

function bool(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function resolveRepoPath(input: string): string {
  const candidate = path.isAbsolute(input) ? input : path.join(ROOT_DIR, input);
  const resolved = path.resolve(candidate);
  if (resolved !== ROOT_DIR && !resolved.startsWith(`${ROOT_DIR}${path.sep}`)) {
    throw new Error(`Path escapes repository root: ${input}`);
  }
  return resolved;
}

async function runPython(args: string[]): Promise<void> {
  const python = existsSync(path.join(ROOT_DIR, ".venv/bin/python"))
    ? path.join(ROOT_DIR, ".venv/bin/python")
    : "python";
  await execFileAsync(python, args, {
    cwd: ROOT_DIR,
    maxBuffer: 1024 * 1024 * 20
  });
}

export async function GET(): Promise<NextResponse> {
  try {
    const payload = await buildDashboardPayload();
    return NextResponse.json(payload, {
      status: 200,
      headers: {
        "Cache-Control": "no-store"
      }
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Failed to load trading dashboard data.",
        message: error instanceof Error ? error.message : "Unknown server error."
      },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const raw = (await request.json()) as RunRequest;
    const csvPathInput = str(raw.csvPath, "data/hyperliquid_btc_1h.csv");
    const csv4hPathInput = str(raw.csv4hPath, "data/hyperliquid_btc_4h.csv");
    const timeframe = str(raw.timeframe, "1h");
    const fillMissing = bool(raw.fillMissing, true);
    const carryEnabled = bool(raw.carryEnabled, true);
    const runDir = "out/next-dashboard";
    const runDirAbs = path.join(ROOT_DIR, runDir);
    const configPath = path.join(runDirAbs, "runtime_config.json");
    const csvPath = resolveRepoPath(csvPathInput);
    const csv4hPath = resolveRepoPath(csv4hPathInput);

    if (!existsSync(csvPath)) {
      return NextResponse.json({ error: `CSV not found: ${csvPathInput}` }, { status: 400 });
    }

    await mkdir(runDirAbs, { recursive: true });

    const runtimeConfig = {
      data: {
        timeframe,
        fill_missing: fillMissing
      },
      guidance: {
        aggressiveness: num(raw.aggressiveness, 0.5),
        ...(carryEnabled
          ? {}
          : {
              risk_off_carry: [0, 0],
              neutral_carry: [0, 0],
              risk_on_carry: [0, 0]
            })
      },
      risk: {
        leverage_cap: num(raw.leverageCap, 1.5),
        venue_cap_frac: num(raw.venueCapFrac, 0.3),
        max_drawdown: num(raw.maxDrawdown, 0.2),
        kill_switch_action: carryEnabled ? "carry_only" : "flat"
      },
      sim: {
        initial_nav: num(raw.initialNav, 10_000),
        liquidation_buffer: num(raw.liquidationBuffer, 0.1),
        target_dir_vol: num(raw.targetDirVol, 0.2),
        order_latency_bars: num(raw.orderLatencyBars, 1),
        fill_range_position: num(raw.fillRangePosition, 0.75),
        fill_time_fraction: num(raw.fillTimeFraction, 0.25),
        directional_stop_loss_pct: num(raw.directionalStopLossPct, 0.02),
        directional_take_profit_pct: num(raw.directionalTakeProfitPct, 0.04),
        directional_max_hold_bars: num(raw.directionalMaxHoldBars, 24),
        carry_rebalance_threshold_pct: num(raw.carryRebalanceThresholdPct, 0.01)
      },
      fees: {
        taker_fee_bps: num(raw.takerFeeBps, 5),
        slippage_bps_at_1x_nav: num(raw.slippageBpsAt1xNav, 10)
      },
      shadow: {
        target_directional_vol: num(raw.targetDirVol, 0.2)
      },
      live: {
        initial_equity: num(raw.initialNav, 10_000)
      }
    };

    await writeFile(configPath, JSON.stringify(runtimeConfig, null, 2), "utf8");

    const fillArg = fillMissing ? ["--fill-missing"] : ["--no-fill-missing"];
    const outputPaths: DashboardCsvPaths = {
      bars: `${runDir}/bars.csv`,
      metrics: `${runDir}/metrics.csv`,
      trades: `${runDir}/trades.csv`,
      lifecycles: `${runDir}/lifecycle.csv`,
      shadow: `${runDir}/shadow_log.csv`,
      taFeatures: `${runDir}/ta_features.csv`
    };

    await runPython([
      "-m",
      "ssh_trader.backtest.run",
      "--csv",
      csvPath,
      "--timeframe",
      timeframe,
      "--config",
      configPath,
      ...fillArg,
      "--output-metrics",
      path.join(ROOT_DIR, outputPaths.metrics),
      "--output-bars",
      path.join(ROOT_DIR, outputPaths.bars),
      "--output-trades",
      path.join(ROOT_DIR, outputPaths.trades),
      "--output-lifecycle",
      path.join(ROOT_DIR, outputPaths.lifecycles)
    ]);

    await runPython([
      "-m",
      "ssh_trader.live.shadow_runner",
      "--csv",
      csvPath,
      "--timeframe",
      timeframe,
      "--config",
      configPath,
      ...(fillMissing ? ["--fill-missing"] : []),
      "--output",
      path.join(ROOT_DIR, outputPaths.shadow)
    ]);

    if (existsSync(csv4hPath)) {
      await runPython([
        "scripts/dump_ta_features.py",
        "--csv-1h",
        csvPath,
        "--csv-4h",
        csv4hPath,
        ...(fillMissing ? ["--fill-missing"] : []),
        "--output",
        path.join(ROOT_DIR, outputPaths.taFeatures)
      ]);
    } else {
      await runPython([
        "scripts/dump_ta_features.py",
        "--csv-1h",
        csvPath,
        ...(fillMissing ? ["--fill-missing"] : []),
        "--output",
        path.join(ROOT_DIR, outputPaths.taFeatures)
      ]);
    }

    const payload = await buildDashboardPayload(outputPaths);
    return NextResponse.json(payload, { status: 200 });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Simulation run failed.",
        message: error instanceof Error ? error.message : "Unknown server error."
      },
      { status: 500 }
    );
  }
}
