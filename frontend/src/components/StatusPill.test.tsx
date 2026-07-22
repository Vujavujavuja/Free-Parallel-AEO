import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import StatusPill from "./StatusPill";

describe("StatusPill", () => {
  it("humanizes the status text", () => {
    render(<StatusPill status="running_models" />);
    expect(screen.getByText("running models")).toBeTruthy();
  });

  it("renders an unknown status without crashing", () => {
    render(<StatusPill status="mystery" />);
    expect(screen.getByText("mystery")).toBeTruthy();
  });
});
