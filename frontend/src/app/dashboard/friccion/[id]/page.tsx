import { Suspense } from "react";
import { notFound } from "next/navigation";
import { FriccionRepository } from "@/repositories/friccion.repository";
import { FrictionDetailView } from "@/components/dashboard/friction-detail/friction-detail-view";

interface FrictionDetailPageProps {
  params: Promise<{ id: string }>;
  searchParams?: Promise<{ event?: string }>;
}

export default async function FrictionDetailPage({
  params,
  searchParams,
}: FrictionDetailPageProps) {
  const { id } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const data = await FriccionRepository.getDetailById(id);

  if (!data) {
    notFound();
  }

  return (
    <Suspense fallback={<div className="w-full min-h-screen bg-[#FAF9F5]" />}>
      <FrictionDetailView data={data} eventId={resolvedSearchParams?.event} />
    </Suspense>
  );
}
