import type { FundTickerHolding } from "./data/types";

/** The four kinds of quarter move: what came in, what grew, what shrank, what left. */
export type MoveFilter = "new" | "increased" | "decreased" | "closed";

/** Which holders of a stock each kind of move covers: the moves panel's groups and the table filter. */
export const HOLDER_MOVE_PICK: Record<MoveFilter, (h: FundTickerHolding) => boolean> = {
  new: (h) => h.isNew,
  increased: (h) => h.isBuyer && !h.isNew,
  decreased: (h) => h.isSeller && !h.isClosed,
  closed: (h) => h.isClosed,
};
