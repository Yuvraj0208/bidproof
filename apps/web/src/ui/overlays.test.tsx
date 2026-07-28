// The Modal is the last thing standing between a click and an irreversible
// delete, and it had no coverage. Bulk delete now sits behind it, so its
// open/close contract is worth pinning down.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Modal } from "./overlays";

describe("Modal", () => {
  it("shows nothing while closed", () => {
    render(
      <Modal open={false} title="Delete 3 tenders?" onClose={() => {}}>
        body
      </Modal>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("names itself so the action is unambiguous", () => {
    render(
      <Modal open title="Delete 3 tenders?" onClose={() => {}}>
        <p>the three titles</p>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-label", "Delete 3 tenders?");
    expect(screen.getByText("the three titles")).toBeInTheDocument();
  });

  it("asks to close on the footer action, without acting itself", () => {
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    render(
      <Modal
        open
        title="Delete 3 tenders?"
        onClose={onClose}
        footer={
          <>
            <button onClick={onClose}>Cancel</button>
            <button onClick={onConfirm}>Delete 3 permanently</button>
          </>
        }
      >
        body
      </Modal>,
    );

    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalledTimes(1);
    // Cancelling must never be mistaken for confirming.
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("closes on a backdrop click", () => {
    const onClose = vi.fn();
    const { container } = render(
      <Modal open title="Delete 3 tenders?" onClose={onClose}>
        body
      </Modal>,
    );
    const backdrop = container.querySelector('[aria-hidden="true"]');
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("confirming is a separate, deliberate click", () => {
    const onConfirm = vi.fn();
    render(
      <Modal
        open
        title="Delete 3 tenders?"
        onClose={() => {}}
        footer={<button onClick={onConfirm}>Delete 3 permanently</button>}
      >
        body
      </Modal>,
    );
    fireEvent.click(screen.getByText("Delete 3 permanently"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
