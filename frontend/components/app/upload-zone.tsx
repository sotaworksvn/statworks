"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useAppStore } from "@/lib/store";
import { uploadFile } from "@/lib/api";
import { toast } from "sonner";
import * as XLSX from "xlsx";

const ACCEPTED_TYPES: Record<string, string[]> = {
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
};

/**
 * Parse an Excel or CSV file locally using SheetJS.
 * Returns { columns, rows } for immediate rendering in Data Viewer.
 */
function parseLocally(
  file: File,
  buffer: ArrayBuffer,
): { columns: string[]; rows: Record<string, unknown>[] } | null {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (ext !== ".xlsx" && ext !== ".csv") return null; // only parse data files

  try {
    const workbook = XLSX.read(buffer, { type: "array" });
    const sheetName = workbook.SheetNames[0];
    if (!sheetName) return null;
    const sheet = workbook.Sheets[sheetName];
    const jsonData = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, {
      defval: "",
    });
    const columns = jsonData.length > 0 ? Object.keys(jsonData[0]) : [];
    return { columns, rows: jsonData };
  } catch {
    return null; // parsing failure is non-fatal — server will handle it
  }
}

export function UploadZone() {
  const { setUploadState, setIsUploading, addUploadedFile, setLocalParsedData, user } =
    useAppStore();

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;

      setIsUploading(true);

      // ─── Strategy 2: Parse locally with SheetJS (instant) ────────
      const primaryFile = acceptedFiles[0];
      const buffer = await primaryFile.arrayBuffer();
      const localData = parseLocally(primaryFile, buffer);

      try {
        // Upload to backend (for AI analysis + R2 persistence)
        const result = await uploadFile(acceptedFiles, user?.id);

        setUploadState({
          fileId: result.file_id,
          datasetName: primaryFile.name,
          rowCount: result.row_count,
          columns: [...result.columns],
        });

        // Register file in uploadedFiles for Data Viewer tabs
        const ext = primaryFile.name.slice(primaryFile.name.lastIndexOf(".")).toLowerCase();
        addUploadedFile({
          id: result.file_id,
          name: primaryFile.name,
          type: ext,
          content_hash: null,
          uploaded_at: new Date().toISOString(),
          columns: [...result.columns],
          row_count: result.row_count,
        });

        // Store locally-parsed data for instant Data Viewer rendering
        if (localData) {
          setLocalParsedData(result.file_id, localData);
        }

        toast.success("Dataset uploaded successfully!");
      } catch (err) {
        const message = err instanceof Error ? err.message : "Upload failed";
        toast.error(message);
      } finally {
        setIsUploading(false);
      }
    },
    [setUploadState, setIsUploading, addUploadedFile, setLocalParsedData, user],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 20 * 1024 * 1024, // 20 MB (per PRD v0.4)
    onDropRejected: (rejections) => {
      const firstError = rejections[0]?.errors[0];
      if (firstError?.code === "file-too-large") {
        toast.error("File exceeds the 20 MB limit.");
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
            or click to browse · .xlsx, .csv, .docx, .pptx · Max 20 MB
          </p>
        </div>
      </div>
    </div>
  );
}
