import { createContext, useContext } from "react";

/**
 * Where floating layers (Radix select menus, tooltips) mount. Outside a modal: the body, as
 * Radix does by default. Inside a native modal `<dialog>`: the dialog itself, because
 * `showModal()` makes everything outside it inert and paints it below the top layer, so a
 * menu portalled to the body could neither be seen nor chosen.
 */
export const PortalContainerContext = createContext<HTMLElement | null>(null);

/** The element floating layers portal into, or undefined for Radix's default (the body). */
export function usePortalContainer(): HTMLElement | undefined {
  return useContext(PortalContainerContext) ?? undefined;
}
