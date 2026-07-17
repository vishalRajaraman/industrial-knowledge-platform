"use client";

import { ProtectedRoute } from "@/components/auth/protected-route";
import { SearchPortal } from "@/components/search/search-portal";

export default function SearchPage() {
  return (
    <ProtectedRoute allowedRoles={["manager", "engineer"]}>
      <SearchPortal />
    </ProtectedRoute>
  );
}
