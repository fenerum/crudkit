import { act, render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, test } from "vitest";
import { ScreenProvider, screenFromLocation, useScreen, useScreenContext } from "./ScreenContext";

describe("screenFromLocation", () => {
  test("detail page", () => {
    expect(screenFromLocation("/CUS12", "?tab=inline-TIC")).toEqual({
      path: "/CUS12",
      route: "detail",
      record_id: "CUS12",
      type_id: "CUS",
      tab: "inline-TIC",
    });
  });

  test("list page with view, search, page and filters", () => {
    expect(screenFromLocation("/CUS/VIW/VIW3", "?q=acme&page=2&page_size=50&status=active")).toEqual({
      path: "/CUS/VIW/VIW3",
      route: "list",
      type_id: "CUS",
      view_id: "VIW3",
      q: "acme",
      page: 2,
      filters: { status: "active" },
    });
  });

  test("dashboard, inbox and other pages", () => {
    expect(screenFromLocation("/", "").route).toBe("dashboard");
    expect(screenFromLocation("/inbox", "?tab=all").route).toBe("inbox");
    expect(screenFromLocation("/CUS/create", "").route).toBe("other");
  });
});

describe("useScreenContext", () => {
  let screen: Record<string, unknown> = {};
  function Reader() {
    screen = useScreen();
    return null;
  }
  function Publisher(props: { partial: Record<string, unknown> }) {
    useScreenContext(props.partial);
    return null;
  }

  test("merges published keys over the URL and removes them on unmount", () => {
    const tree = (publisher: React.ReactNode) => (
      <MemoryRouter initialEntries={["/CUS"]}>
        <ScreenProvider>
          {publisher}
          <Reader />
        </ScreenProvider>
      </MemoryRouter>
    );
    const { rerender } = render(tree(<Publisher partial={{ view_id: "VIW1", selected_ids: ["CUS1"] }} />));
    expect(screen).toMatchObject({ route: "list", type_id: "CUS", view_id: "VIW1", selected_ids: ["CUS1"] });

    act(() => rerender(tree(<Publisher partial={{ selected_ids: [] }} />)));
    expect(screen.view_id).toBeUndefined();
    expect(screen.selected_ids).toEqual([]);

    act(() => rerender(tree(null)));
    expect(screen.selected_ids).toBeUndefined();
  });
});
