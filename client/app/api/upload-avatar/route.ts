import { NextRequest, NextResponse } from "next/server";
import { writeFile, mkdir } from "fs/promises";
import path from "path";
import { fileTypeFromBuffer } from "file-type";
import { auth } from "@/lib/auth";
import { headers } from "next/headers";

const ALLOWED_MIME_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
]);
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

export async function POST(request: NextRequest) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session?.user) {
    return NextResponse.json(
      { error: "ログインが必要です。ログインし直してください" },
      { status: 401 },
    );
  }

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json(
      { error: "リクエストの解析に失敗しました" },
      { status: 400 },
    );
  }
  const file = formData.get("file");

  if (!(file instanceof File)) {
    return NextResponse.json(
      { error: "ファイルが見つかりません" },
      { status: 400 },
    );
  }

  // Early reject by declared MIME type before reading the buffer
  if (!ALLOWED_MIME_TYPES.has(file.type)) {
    return NextResponse.json(
      { error: "JPEG, PNG, WebP, GIF のみアップロード可能です" },
      { status: 400 },
    );
  }

  if (file.size > MAX_FILE_SIZE) {
    return NextResponse.json(
      { error: "ファイルサイズは5MB以下にしてください" },
      { status: 400 },
    );
  }

  // Sanitize userId to prevent path traversal (alphanumeric, hyphen, underscore only)
  const safeUserId = session.user.id.replace(/[^a-zA-Z0-9_-]/g, "");
  if (!safeUserId) {
    return NextResponse.json(
      { error: "リクエストが正しくありません。もう一度お試しください" },
      { status: 400 },
    );
  }

  const buffer = Buffer.from(await file.arrayBuffer());

  // Validate actual file content via magic bytes — file.type is client-declared and untrustworthy
  const detected = await fileTypeFromBuffer(buffer);
  if (!detected || !ALLOWED_MIME_TYPES.has(detected.mime)) {
    return NextResponse.json(
      { error: "JPEG, PNG, WebP, GIF のみアップロード可能です" },
      { status: 400 },
    );
  }

  // Fixed filename per user — overwrites previous avatar, preventing unbounded disk growth
  const filename = `${safeUserId}.${detected.ext}`;
  const avatarsDir = path.join(process.cwd(), "public", "avatars");
  const filePath = path.join(avatarsDir, filename);

  // Guard: ensure resolved path stays inside avatarsDir (defense-in-depth)
  if (!filePath.startsWith(avatarsDir + path.sep)) {
    return NextResponse.json(
      { error: "リクエストが正しくありません。もう一度お試しください" },
      { status: 400 },
    );
  }

  try {
    await mkdir(avatarsDir, { recursive: true });
    await writeFile(filePath, buffer);
  } catch (e) {
    console.error("avatar upload write failed", e);
    return NextResponse.json(
      { error: "写真をアップロードできませんでした。もう一度お試しください" },
      { status: 500 },
    );
  }

  return NextResponse.json({ url: `/avatars/${filename}` });
}
