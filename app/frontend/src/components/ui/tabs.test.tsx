import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

describe("findable TabsContent", () => {
  it("shows the selected panel and keeps the others findable but hidden", async () => {
    render(
      <Tabs defaultValue="one">
        <TabsList>
          <TabsTrigger value="one">One</TabsTrigger>
          <TabsTrigger value="two">Two</TabsTrigger>
        </TabsList>
        <TabsContent value="one" findable>
          first panel
        </TabsContent>
        <TabsContent value="two" findable>
          second panel
        </TabsContent>
      </Tabs>,
    );

    // Radix triggers select on mousedown.
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Two" }), { button: 0 });

    const second = screen.getByText("second panel").closest('[role="tabpanel"]');
    const first = screen.getByText("first panel").closest('[role="tabpanel"]');
    await waitFor(() => expect(second?.hasAttribute("hidden")).toBe(false));
    expect(first?.getAttribute("hidden")).toBe("until-found");
  });
});
