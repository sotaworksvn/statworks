"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useAppStore } from "@/lib/store";
import { uploadFile } from "@/lib/api";
import { toast } from "sonner";

const ACCEPTED_TYPES: Record<string, string[]> = {
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
};

export function UploadZone() {
  const { setUploadState, setIsUploading, user } = useAppStore();

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;

      setIsUploading(true);
      try {
        // Pass clerkUserId for x-clerk-user-id header
        const result = await uploadFile(acceptedFiles, user?.id);
        setUploadState({
          fileId: result.file_id,
          datasetName: acceptedFiles[0].name,
          rowCount: result.row_count,
          columns: [...result.columns],
        });
        toast.success("Dataset uploaded successfully!");
      } catch (err) {
        const message = err instanceof Error ? err.message : "Upload failed";
        toast.error(message);
      } finally {
        setIsUploading(false);
      }
    },
    [setUploadState, setIsUploading, user]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 10 * 1024 * 1024, // 10 MB
    onDropRejected: (rejections) => {
      const firstError = rejections[0]?.errors[0];
      if (firstError?.code === "file-too-large") {
        toast.error("File exceeds the 10 MB limit.");
      } else if (firstError?.code === "file-invalid-type") {
        toast.error("Unsupported file type. Allowed: .xlsx, .csv, .docx, .pptx");
      } else {
        toast.error(firstError?.message ?? "File rejected");
      }
    },
  });

  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <div
        {...getRootProps()}
        id="upload-zone"
        className={`flex w-full max-w-xl flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer transition-all ${
          isDragActive
            ? "border-[#FF6B4A] bg-[#FF6B4A]/5"
            : "border-gray-200 bg-[#F5F5F7]/50 hover:border-[#2D3561]/30 hover:bg-[#F5F5F7]"
        }`}
      >
        <input {...getInputProps()} />

        <div className="text-5xl">📁</div>

        <div>
          <p className="font-semibold text-[#2D3561] text-lg mb-1">
            {isDragActive ? "Drop your file here" : "Drag & drop your dataset"}
          </p>
          <p className="text-gray-400 text-sm">
            or click to browse · .xlsx, .csv, .docx, .pptx · Max 10 MB
          </p>
        </div>
      </div>
    </div>
  );
}
