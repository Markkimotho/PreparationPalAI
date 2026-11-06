import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeAll } from "vitest";
import { Guide } from "../sections/Guide";
import { GUIDE } from "../sections/Guide/content";

beforeAll(() => {
  // jsdom lacks these; the Guide uses them for scroll/observe.
  // @ts-expect-error - test shim
  window.IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  Element.prototype.scrollIntoView = () => {};
});

describe("Guide", () => {
  it("renders a table of contents grouped by section group", () => {
    render(<Guide />);
    expect(screen.getByText("Core features")).toBeInTheDocument();
    expect(screen.queryByText("Developer")).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Full user guide ↗' })).toHaveAttribute('href', 'https://markkimotho.github.io/PreparationPalAI/');
  });

  it("renders every guide section's content", () => {
    render(<Guide />);
    // Each section's title appears at least once (in the TOC).
    for (const s of GUIDE) {
      expect(screen.getAllByText(s.title).length).toBeGreaterThan(0);
    }
  });

  it("keeps engineering instructions outside the learner guide", () => {
    render(<Guide />);
    expect(screen.queryByText(/Using Loki/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/compose_service/, { exact: false })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Contribute to the project ↗' })).toHaveAttribute('href', 'https://markkimotho.github.io/PreparationPalAI/contribute/');
  });

  it("TOC entries are clickable buttons", async () => {
    render(<Guide />);
    const tocButton = screen.getByRole("button", { name: "Preparation Coach" });
    await userEvent.click(tocButton);
    expect(tocButton).toBeInTheDocument();
  });
});
