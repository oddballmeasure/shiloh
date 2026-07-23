import { AssignmentWorkspace } from "@/components/assignment-workspace";
import { backendFetch, requireSession } from "@/lib/server-api";
import type { Assignment } from "@/lib/types";

export default async function AssignmentPage({
  params,
}: {
  params: Promise<{ assignmentId: string }>;
}) {
  const { assignmentId } = await params;
  const session = await requireSession();
  const assignment = await backendFetch<Assignment>(
    `/api/assignments/${assignmentId}`,
    {},
    session.backendToken,
  );

  return <AssignmentWorkspace assignment={assignment} />;
}
