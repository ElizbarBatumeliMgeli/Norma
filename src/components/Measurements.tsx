import type { Floor, Mark } from "../lib/api";
import { useI18n } from "../lib/i18n";

type Value = { text: string; mark?: Mark; state?: "bad" | "warn" };

const m = (value: number | null | undefined, digits = 2) => (value == null ? "" : value.toFixed(digits));

function cells(floor: Floor): Value[] {
  const { marks } = floor;
  const hasStairs = floor.stairs > 0;
  return [
    { text: floor.level == null ? "" : `${floor.level >= 0 ? "+" : ""}${floor.level.toFixed(2)}` },
    { text: String(floor.stairs), mark: marks.stairs, state: floor.stairs < 2 ? "warn" : undefined },
    { text: hasStairs ? m(floor.stair_width) : "", mark: marks.stairs, state: (floor.stair_width ?? 9) < 1.1 ? "bad" : undefined },
    {
      text: floor.riser && floor.tread ? `${Math.round(floor.riser * 100)} × ${Math.round(floor.tread * 100)}` : floor.tread ? `${Math.round(floor.tread * 100)}` : "",
      mark: marks.stairs,
      state: (floor.tread ?? 9) < 0.278 || (floor.riser ?? 0) > 0.18 ? "bad" : undefined,
    },
    {
      text: floor.separation_outer == null ? "" : `${m(floor.separation_outer, 1)}–${m(floor.separation_inner, 1)}`,
      mark: marks.separation,
      state: (floor.separation_outer ?? 99) < 9 ? "warn" : undefined,
    },
    { text: floor.corridor == null ? "" : `≈ ${m(floor.corridor, 1)}`, mark: marks.corridor, state: (floor.narrowest ?? 9) < 1.2 ? "warn" : undefined },
    { text: floor.dead_end == null ? "" : `≈ ${m(floor.dead_end, 1)}`, mark: marks.corridor, state: (floor.dead_end ?? 0) > 6 ? "warn" : undefined },
    { text: floor.sprinklers ? String(floor.sprinklers) : "" },
    { text: floor.cabinets ? String(floor.cabinets) : "" },
  ];
}

const COLUMNS = ["colLevel", "colStairs", "colFlight", "colStep", "colApart", "colCorridor", "colDeadEnd", "colSprinklers", "colCabinets"];

/** The building storey by storey: what was read from the CAD files. A value opens its place on the drawing. */
export default function Measurements({ floors, onFocus }: { floors: Floor[]; onFocus: (mark: Mark) => void }) {
  const { t } = useI18n();
  return (
    <div className="measured">
      <div className="measured-scroll">
        <table className="measured-table">
          <thead>
            <tr>
              <th scope="col">{t("colFloor")}</th>
              {COLUMNS.map((key) => (
                <th key={key} scope="col">
                  {t(key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...floors].reverse().map((floor) => (
              <tr key={floor.name}>
                <th scope="row">
                  <button type="button" className="measured-floor" onClick={() => onFocus({ page: floor.page, box: null })}>
                    {floor.name}
                  </button>
                </th>
                {cells(floor).map((cell, index) => (
                  <td key={COLUMNS[index]} className={cell.state ? `is-${cell.state}` : undefined}>
                    {cell.mark && cell.text ? (
                      <button type="button" className="measured-value" onClick={() => onFocus(cell.mark!)}>
                        {cell.text}
                      </button>
                    ) : (
                      cell.text || <span className="measured-none">–</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="legal-note">{t("measuredNote")}</p>
    </div>
  );
}
