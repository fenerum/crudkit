import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, test, vi } from "vitest";
import { FeedItem } from "./Feed";

vi.mock("../data/api", () => {
  class Client {
    async retrieve() { return {}; }
  }
  return { default: Client };
});

vi.mock("../context/AuthContext", () => ({ useAuth: () => ({ user: null }) }));

describe("FeedItem", () => {
  test("renders the feed item body for a non-email related object", () => {
    const object = {
      id: "FEI1",
      related_object: "MSG1",
      related_content_type: { app_label: "crm", model: "message" },
      body: "<p>Hello from chat</p>",
      created_at: "2026-09-21T10:00:00Z",
      created_by: null,
    };
    const { container } = render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <FeedItem object={object} model="COM" sendEmailAction={vi.fn()} onReply={vi.fn()} isReplyTarget={false} />
        </MemoryRouter>
      </QueryClientProvider>
    );
    expect(container.querySelector("iframe")?.getAttribute("srcdoc")).toContain("<p>Hello from chat</p>");
  });
});
