import { AssignmentManager } from "@/components/assignment-manager";
import { backendFetch, requireSession } from "@/lib/server-api";
import type { Assignment } from "@/lib/types";

type AssignmentView = "all" | "available" | "create";

function normalizeView(value: string | string[] | undefined): AssignmentView {
  if (value === "available" || value === "create" || value === "all") {
    return value;
  }
  return "all";
}

export default async function AssignmentsPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await requireSession();
  const params = (await searchParams) ?? {};
  const initialView = normalizeView(params.view);
  const assignments = await backendFetch<Assignment[]>("/api/assignments", {}, session.backendToken);

  return <AssignmentManager initialAssignments={assignments} initialView={initialView} />;
}
