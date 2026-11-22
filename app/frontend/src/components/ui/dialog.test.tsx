import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

describe("Dialog", () => {
  it("mounts a select menu opened in a modal inside the dialog, not in the inert page", () => {
    render(
      <Dialog open onOpenChange={() => {}}>
        <DialogContent>
          <DialogTitle>Add AI Model</DialogTitle>
          <Select open defaultValue="openai">
            <SelectTrigger aria-label="Provider">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="openai">OpenAI</SelectItem>
              <SelectItem value="google">Google</SelectItem>
            </SelectContent>
          </Select>
        </DialogContent>
      </Dialog>,
    );
    const dialog = screen.getByRole("dialog", { name: "Add AI Model" });
    expect(dialog.contains(screen.getByRole("listbox"))).toBe(true);
  });
});
