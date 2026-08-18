import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TransactionCategoryEditor } from "@/components/finance/TransactionCategoryEditor";

const post = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    post: (...args: unknown[]) => post(...args),
  },
}));

describe("TransactionCategoryEditor", () => {
  beforeEach(() => {
    post.mockReset();
  });

  it("changes to an existing scoped category", async () => {
    const onUpdated = vi.fn();
    post.mockResolvedValue({
      category: "Fuel",
      category_confidence: "HIGH",
    });

    render(
      <TransactionCategoryEditor
        txnId={42}
        scope="personal"
        category="Food"
        options={[
          { parent: "Food", scope: "personal" },
          { parent: "Fuel", scope: "personal" },
          { parent: "VAT", scope: "business" },
        ]}
        canEdit
        onUpdated={onUpdated}
        onError={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /edit category/i }));
    fireEvent.change(screen.getByLabelText("Choose category"), {
      target: { value: "Fuel" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/finance/transactions/42/category", {
        category: "Fuel",
      }),
    );
    expect(onUpdated).toHaveBeenCalledWith({
      category: "Fuel",
      category_confidence: "HIGH",
    });
    expect(screen.queryByText("VAT")).not.toBeInTheDocument();
  });

  it("adds a new category name and assigns it", async () => {
    const onUpdated = vi.fn();
    post.mockResolvedValue({
      category: "Dog walking",
      category_confidence: "HIGH",
    });

    render(
      <TransactionCategoryEditor
        txnId={9}
        scope="business"
        category="Office costs"
        options={[
          { parent: "Office costs", scope: "business" },
          { parent: "Food", scope: "personal" },
        ]}
        canEdit
        onUpdated={onUpdated}
        onError={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /edit category/i }));
    fireEvent.change(screen.getByLabelText("Choose category"), {
      target: { value: "__new__" },
    });
    fireEvent.change(screen.getByLabelText("New category name"), {
      target: { value: "Dog walking" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/finance/transactions/9/category", {
        category: "Dog walking",
      }),
    );
    expect(onUpdated).toHaveBeenCalledWith({
      category: "Dog walking",
      category_confidence: "HIGH",
    });
  });

  it("renders read-only text when editing is disabled", () => {
    render(
      <TransactionCategoryEditor
        txnId={1}
        scope="personal"
        category="Food"
        options={[{ parent: "Food", scope: "personal" }]}
        canEdit={false}
        onUpdated={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.getByText("Food")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit category/i })).not.toBeInTheDocument();
  });
});
