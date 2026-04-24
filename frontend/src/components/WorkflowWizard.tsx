"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import {
  Globe,
  Search,
  Upload,
  Play,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Eye,
  Edit2,
  FileText,
  ClipboardPaste,
  StopCircle,
  RefreshCw,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────

interface DetectedFields {
  page_title?: string;
  username_selector: string;
  username_label: string;
  password_selector: string;
  password_label: string;
  submit_selector: string;
  submit_label: string;
  form_action: string;
  extra_fields: { selector: string; type: string; label: string; name: string }[];
  confidence: number;
  all_inputs: any[];
}

interface Workflow {
  id: string;
  name: string;
  target_url: string;
  description?: string;
  status: string;
  detected_fields: DetectedFields;
  custom_selectors: Record<string, any>;
  credentials_file?: string;
  credential_count: number;
  delay_between_logins: number;
  use_stealth: boolean;
  max_retries: number;
  success_indicators: Record<string, any>;
  total_credentials: number;
  processed_count: number;
  successful_count: number;
  failed_count: number;
  results: {
    username: string;
    status: string;
    message: string;
    final_url?: string;
    timestamp?: string;
    attempt?: number;
  }[];
  created_at: string;
  updated_at: string;
}

type Step = "url" | "review" | "upload" | "run";

const STEPS: { key: Step; label: string; icon: React.ReactNode }[] = [
  { key: "url", label: "Enter URL", icon: <Globe className="h-4 w-4" /> },
  { key: "review", label: "Review Fields", icon: <Eye className="h-4 w-4" /> },
  { key: "upload", label: "Upload Credentials", icon: <Upload className="h-4 w-4" /> },
  { key: "run", label: "Run Automation", icon: <Play className="h-4 w-4" /> },
];

// ── Component ────────────────────────────────────────────────────────

export default function WorkflowWizard({
  onBack,
}: {
  onBack: () => void;
}) {
  const [step, setStep] = useState<Step>("url");
  const [url, setUrl] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState("");
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [useStealth, setUseStealth] = useState(true);

  // Editable selectors (override detected)
  const [editSelectors, setEditSelectors] = useState(false);
  const [usernameSelector, setUsernameSelector] = useState("");
  const [passwordSelector, setPasswordSelector] = useState("");
  const [submitSelector, setSubmitSelector] = useState("");

  // Credentials
  const [credMode, setCredMode] = useState<"file" | "paste">("paste");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [credentialCount, setCredentialCount] = useState(0);
  const [sampleUsernames, setSampleUsernames] = useState<string[]>([]);
  const [pasteText, setPasteText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Execution
  const [running, setRunning] = useState(false);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // ── Step 1: Scan URL ──────────────────────────────────────────────

  const handleScan = async () => {
    if (!url.trim()) return;
    setScanning(true);
    setScanError("");
    try {
      const res = await fetch("/api/workflows/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Scan failed");
      }
      const data = await res.json();
      // Fetch full workflow
      const wfRes = await fetch(`/api/workflows/${data.workflow_id}`);
      const wf: Workflow = await wfRes.json();
      setWorkflow(wf);
      setUseStealth(wf.use_stealth);
      setUsernameSelector(wf.detected_fields.username_selector);
      setPasswordSelector(wf.detected_fields.password_selector);
      setSubmitSelector(wf.detected_fields.submit_selector);
      setStep("review");
    } catch (e: any) {
      setScanError(e.message);
    } finally {
      setScanning(false);
    }
  };

  // ── Step 2: Save custom selectors ─────────────────────────────────

  const saveSelectors = async () => {
    if (!workflow) return;
    await fetch(`/api/workflows/${workflow.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        custom_selectors: {
          username_selector: usernameSelector,
          password_selector: passwordSelector,
          submit_selector: submitSelector,
        },
      }),
    });
    setEditSelectors(false);
  };

  // ── Step 3: Upload credentials ────────────────────────────────────

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !workflow) return;
    setUploading(true);
    setUploadError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`/api/workflows/${workflow.id}/credentials`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }
      const data = await res.json();
      setCredentialCount(data.credential_count);
      setSampleUsernames(data.sample_usernames);
      // Refresh workflow
      const wfRes = await fetch(`/api/workflows/${workflow.id}`);
      setWorkflow(await wfRes.json());
    } catch (e: any) {
      setUploadError(e.message);
    } finally {
      setUploading(false);
    }
  };

  // ── Step 3b: Paste credentials ──────────────────────────────────

  const handlePasteSubmit = async () => {
    if (!pasteText.trim() || !workflow) return;
    setUploading(true);
    setUploadError("");
    try {
      const res = await fetch(
        `/api/workflows/${workflow.id}/credentials/paste`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: pasteText }),
        }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to parse credentials");
      }
      const data = await res.json();
      setCredentialCount(data.credential_count);
      setSampleUsernames(data.sample_usernames);
      // Refresh workflow
      const wfRes = await fetch(`/api/workflows/${workflow.id}`);
      setWorkflow(await wfRes.json());
    } catch (e: any) {
      setUploadError(e.message);
    } finally {
      setUploading(false);
    }
  };

  // ── Step 4: Run automation ────────────────────────────────────────

  const handleRun = async () => {
    if (!workflow) return;
    setRunning(true);
    try {
      const res = await fetch(`/api/workflows/${workflow.id}/run`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Start failed");
      }
      // Start polling
      startPolling();
    } catch (e: any) {
      setRunning(false);
      alert(e.message);
    }
  };

  const handleStop = async () => {
    if (!workflow) return;
    await fetch(`/api/workflows/${workflow.id}/stop`, { method: "POST" });
    stopPolling();
    setRunning(false);
    refreshWorkflow();
  };

  const startPolling = () => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      await refreshWorkflow();
    }, 2000);
  };

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const refreshWorkflow = useCallback(async () => {
    if (!workflow) return;
    try {
      const res = await fetch(`/api/workflows/${workflow.id}`);
      const wf: Workflow = await res.json();
      setWorkflow(wf);
      setUseStealth(wf.use_stealth);
      if (wf.status !== "running") {
        setRunning(false);
        stopPolling();
      }
    } catch {
      // ignore
    }
  }, [workflow?.id]);

  useEffect(() => {
    return () => stopPolling();
  }, []);

  // ── Helpers ───────────────────────────────────────────────────────

  const confidenceColor = (c: number) => {
    if (c >= 0.7) return "text-green-600";
    if (c >= 0.4) return "text-yellow-600";
    return "text-red-600";
  };

  const stepIndex = STEPS.findIndex((s) => s.key === step);

  const canProceedToUpload =
    workflow && usernameSelector && passwordSelector;

  const handleStealthToggle = async (enabled: boolean) => {
    setUseStealth(enabled);
    if (!workflow) return;

    await fetch(`/api/workflows/${workflow.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_stealth: enabled }),
    });

    const res = await fetch(`/api/workflows/${workflow.id}`);
    if (res.ok) {
      setWorkflow(await res.json());
    }
  };

  const canProceedToRun =
    workflow && (workflow.credential_count > 0 || credentialCount > 0);

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Back button + title */}
      <div className="flex items-center space-x-4">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back
        </Button>
        <div>
          <h2 className="text-2xl font-bold">New Automation Workflow</h2>
          <p className="text-sm text-muted-foreground">
            Scan a login page, upload credentials, and run bulk automation
          </p>
        </div>
      </div>

      {/* Step indicator */}
      <div className="flex items-center space-x-2">
        {STEPS.map((s, i) => (
          <div key={s.key} className="flex items-center">
            <div
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${
                i < stepIndex
                  ? "bg-green-100 text-green-700"
                  : i === stepIndex
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {i < stepIndex ? (
                <CheckCircle className="h-3.5 w-3.5" />
              ) : (
                s.icon
              )}
              <span>{s.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className="w-8 h-px bg-border mx-1" />
            )}
          </div>
        ))}
      </div>

      {/* ─── Step 1: Enter URL ─── */}
      {step === "url" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Globe className="h-5 w-5" />
              <span>Target URL</span>
            </CardTitle>
            <CardDescription>
              Enter the login page URL. We will scan it to detect the
              username field, password field, and submit button automatically.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex space-x-2">
              <Input
                placeholder="https://example.com/login"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleScan()}
                className="flex-1"
              />
              <Button onClick={handleScan} disabled={scanning || !url.trim()}>
                {scanning ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Search className="h-4 w-4 mr-2" />
                )}
                {scanning ? "Scanning..." : "Scan"}
              </Button>
            </div>
            {scanError && (
              <div className="flex items-center space-x-2 text-sm text-red-600 bg-red-50 p-3 rounded-md">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                <span>{scanError}</span>
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Supported: any page with a login form (email/username + password + submit button)
            </p>
          </CardContent>
        </Card>
      )}

      {/* ─── Step 2: Review detected fields ─── */}
      {step === "review" && workflow && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Eye className="h-5 w-5" />
                <span>Detected Login Form</span>
              </div>
              <Badge
                className={
                  workflow.detected_fields.confidence >= 0.7
                    ? "bg-green-100 text-green-800"
                    : workflow.detected_fields.confidence >= 0.4
                    ? "bg-yellow-100 text-yellow-800"
                    : "bg-red-100 text-red-800"
                }
              >
                {Math.round(workflow.detected_fields.confidence * 100)}% confidence
              </Badge>
            </CardTitle>
            <CardDescription>
              {workflow.detected_fields.page_title && (
                <span>
                  Page: <strong>{workflow.detected_fields.page_title}</strong>
                  {" | "}
                </span>
              )}
              {workflow.target_url}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Username field */}
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                Username / Email Field
              </Label>
              {editSelectors ? (
                <Input
                  value={usernameSelector}
                  onChange={(e) => setUsernameSelector(e.target.value)}
                  placeholder="CSS selector for username field"
                />
              ) : (
                <div className="flex items-center space-x-2">
                  <code className="flex-1 bg-muted px-3 py-2 rounded text-sm font-mono">
                    {usernameSelector || "(not detected)"}
                  </code>
                  {workflow.detected_fields.username_label && (
                    <Badge variant="secondary">
                      {workflow.detected_fields.username_label}
                    </Badge>
                  )}
                </div>
              )}
            </div>

            {/* Password field */}
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                Password Field
              </Label>
              {editSelectors ? (
                <Input
                  value={passwordSelector}
                  onChange={(e) => setPasswordSelector(e.target.value)}
                  placeholder="CSS selector for password field"
                />
              ) : (
                <div className="flex items-center space-x-2">
                  <code className="flex-1 bg-muted px-3 py-2 rounded text-sm font-mono">
                    {passwordSelector || "(not detected)"}
                  </code>
                  {workflow.detected_fields.password_label && (
                    <Badge variant="secondary">
                      {workflow.detected_fields.password_label}
                    </Badge>
                  )}
                </div>
              )}
            </div>

            {/* Submit button */}
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                Submit Button
              </Label>
              {editSelectors ? (
                <Input
                  value={submitSelector}
                  onChange={(e) => setSubmitSelector(e.target.value)}
                  placeholder="CSS selector for submit button"
                />
              ) : (
                <div className="flex items-center space-x-2">
                  <code className="flex-1 bg-muted px-3 py-2 rounded text-sm font-mono">
                    {submitSelector || "(not detected)"}
                  </code>
                  {workflow.detected_fields.submit_label && (
                    <Badge variant="secondary">
                      {workflow.detected_fields.submit_label}
                    </Badge>
                  )}
                </div>
              )}
            </div>

            {/* Advanced anti-bot */}
            <div className="flex items-center justify-between gap-4 rounded border border-dashed border-slate-200 bg-slate-50 p-4">
              <div>
                <p className="text-sm font-medium">Advanced anti-bot mode</p>
                <p className="text-xs text-muted-foreground">
                  Enable stronger browser stealth behavior during login automation.
                </p>
              </div>
              <label className="inline-flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={useStealth}
                  onChange={(e) => handleStealthToggle(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                />
                <span className="text-sm">Enabled</span>
              </label>
            </div>

            {/* Form action */}
            {workflow.detected_fields.form_action && (
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                  Form Action
                </Label>
                <code className="block bg-muted px-3 py-2 rounded text-sm font-mono text-muted-foreground">
                  {workflow.detected_fields.form_action}
                </code>
              </div>
            )}

            {/* Extra fields */}
            {workflow.detected_fields.extra_fields?.length > 0 && (
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                  Other Fields Detected
                </Label>
                <div className="flex flex-wrap gap-2">
                  {workflow.detected_fields.extra_fields.map((f, i) => (
                    <Badge key={i} variant="outline">
                      {f.label || f.name || f.type} ({f.type})
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            <Separator />

            <div className="flex items-center justify-between">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  if (editSelectors) saveSelectors();
                  setEditSelectors(!editSelectors);
                }}
              >
                <Edit2 className="h-3.5 w-3.5 mr-1.5" />
                {editSelectors ? "Save Changes" : "Edit Selectors"}
              </Button>

              <div className="flex space-x-2">
                <Button variant="ghost" onClick={() => setStep("url")}>
                  <ArrowLeft className="h-4 w-4 mr-1" /> Back
                </Button>
                <Button
                  onClick={() => setStep("upload")}
                  disabled={!canProceedToUpload}
                >
                  Continue <ArrowRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ─── Step 3: Credentials ─── */}
      {step === "upload" && workflow && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Upload className="h-5 w-5" />
              <span>Credentials</span>
            </CardTitle>
            <CardDescription>
              Paste credentials directly or upload a file with username:password pairs.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Mode toggle */}
            <div className="flex rounded-lg border p-1 w-fit">
              <button
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  credMode === "paste"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={() => setCredMode("paste")}
              >
                <ClipboardPaste className="h-3.5 w-3.5" />
                <span>Paste</span>
              </button>
              <button
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  credMode === "file"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={() => setCredMode("file")}
              >
                <FileText className="h-3.5 w-3.5" />
                <span>Upload File</span>
              </button>
            </div>

            {/* Paste mode */}
            {credMode === "paste" && (
              <div className="space-y-3">
                <Textarea
                  placeholder={"user1@example.com:password123\nuser2@example.com:pass456\nadmin:hunter2"}
                  value={pasteText}
                  onChange={(e) => setPasteText(e.target.value)}
                  rows={8}
                  className="font-mono text-sm"
                />
                <div className="flex items-center justify-between">
                  <p className="text-xs text-muted-foreground">
                    One per line: username:password, username,password, or CSV with headers
                  </p>
                  <Button
                    size="sm"
                    onClick={handlePasteSubmit}
                    disabled={uploading || !pasteText.trim()}
                  >
                    {uploading ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <CheckCircle className="h-4 w-4 mr-2" />
                    )}
                    {uploading ? "Processing..." : "Load Credentials"}
                  </Button>
                </div>
              </div>
            )}

            {/* File upload mode */}
            {credMode === "file" && (
              <div
                className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".txt,.csv"
                  onChange={handleFileUpload}
                  className="hidden"
                />
                {uploading ? (
                  <Loader2 className="mx-auto h-10 w-10 text-muted-foreground animate-spin" />
                ) : (
                  <FileText className="mx-auto h-10 w-10 text-muted-foreground" />
                )}
                <p className="mt-2 text-sm font-medium">
                  {uploading ? "Uploading..." : "Click to upload credentials file"}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  .txt (username:password per line) or .csv (username,password columns)
                </p>
              </div>
            )}

            {uploadError && (
              <div className="flex items-center space-x-2 text-sm text-red-600 bg-red-50 p-3 rounded-md">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            {/* Credential preview */}
            {credentialCount > 0 && (
              <div className="bg-green-50 border border-green-200 rounded-md p-4 space-y-2">
                <div className="flex items-center space-x-2 text-green-700">
                  <CheckCircle className="h-4 w-4" />
                  <span className="font-medium">
                    {credentialCount} credential pairs loaded
                  </span>
                </div>
                <div className="text-sm text-green-600">
                  <span className="font-medium">Sample usernames:</span>{" "}
                  {sampleUsernames.join(", ")}
                  {credentialCount > 5 && ", ..."}
                </div>
              </div>
            )}

            <Separator />

            <div className="flex items-center justify-between">
              <Button variant="ghost" onClick={() => setStep("review")}>
                <ArrowLeft className="h-4 w-4 mr-1" /> Back
              </Button>
              <Button
                onClick={() => setStep("run")}
                disabled={!canProceedToRun}
              >
                Continue <ArrowRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ─── Step 4: Run Automation ─── */}
      {step === "run" && workflow && (
        <div className="space-y-4">
          {/* Summary card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Play className="h-5 w-5" />
                <span>Run Automation</span>
              </CardTitle>
              <CardDescription>
                Review the configuration and start the login automation.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Target:</span>
                  <p className="font-medium truncate">{workflow.target_url}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Credentials:</span>
                  <p className="font-medium">
                    {workflow.total_credentials || credentialCount} pairs
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Username field:</span>
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                    {usernameSelector}
                  </code>
                </div>
                <div>
                  <span className="text-muted-foreground">Password field:</span>
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                    {passwordSelector}
                  </code>
                </div>
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <Button
                  variant="ghost"
                  onClick={() => setStep("upload")}
                  disabled={running}
                >
                  <ArrowLeft className="h-4 w-4 mr-1" /> Back
                </Button>
                <div className="flex space-x-2">
                  {running || workflow.status === "running" ? (
                    <Button variant="destructive" onClick={handleStop}>
                      <StopCircle className="h-4 w-4 mr-2" /> Stop
                    </Button>
                  ) : (
                    <Button onClick={handleRun}>
                      <Play className="h-4 w-4 mr-2" /> Start Automation
                    </Button>
                  )}
                  {(workflow.status === "completed" ||
                    workflow.status === "failed" ||
                    workflow.status === "stopped") && (
                    <Button variant="outline" onClick={handleRun}>
                      <RefreshCw className="h-4 w-4 mr-2" /> Re-run
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Progress + Results */}
          {(workflow.status === "running" ||
            workflow.status === "completed" ||
            workflow.status === "failed" ||
            workflow.status === "stopped") && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Execution Progress</span>
                  <Badge
                    className={
                      workflow.status === "running"
                        ? "bg-blue-100 text-blue-800"
                        : workflow.status === "completed"
                        ? "bg-green-100 text-green-800"
                        : workflow.status === "stopped"
                        ? "bg-yellow-100 text-yellow-800"
                        : "bg-red-100 text-red-800"
                    }
                  >
                    {workflow.status}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Progress bar */}
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>
                      Processed: {workflow.processed_count} /{" "}
                      {workflow.total_credentials}
                    </span>
                    <span>
                      {workflow.total_credentials > 0
                        ? Math.round(
                            (workflow.processed_count /
                              workflow.total_credentials) *
                              100
                          )
                        : 0}
                      %
                    </span>
                  </div>
                  <Progress
                    value={
                      workflow.total_credentials > 0
                        ? (workflow.processed_count /
                            workflow.total_credentials) *
                          100
                        : 0
                    }
                  />
                </div>

                {/* Stats row */}
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div className="bg-green-50 rounded-md p-3 text-center">
                    <div className="text-green-700 font-bold text-lg">
                      {workflow.successful_count}
                    </div>
                    <div className="text-green-600 text-xs">Successful</div>
                  </div>
                  <div className="bg-red-50 rounded-md p-3 text-center">
                    <div className="text-red-700 font-bold text-lg">
                      {workflow.failed_count}
                    </div>
                    <div className="text-red-600 text-xs">Failed</div>
                  </div>
                  <div className="bg-blue-50 rounded-md p-3 text-center">
                    <div className="text-blue-700 font-bold text-lg">
                      {workflow.total_credentials - workflow.processed_count}
                    </div>
                    <div className="text-blue-600 text-xs">Remaining</div>
                  </div>
                </div>

                {/* Results table */}
                {workflow.results.length > 0 && (
                  <>
                    <Separator />
                    <div className="space-y-1">
                      <h4 className="text-sm font-medium">Results Log</h4>
                      <div className="max-h-64 overflow-y-auto rounded border">
                        <table className="w-full text-sm">
                          <thead className="bg-muted sticky top-0">
                            <tr>
                              <th className="text-left px-3 py-2 font-medium">
                                Username
                              </th>
                              <th className="text-left px-3 py-2 font-medium">
                                Status
                              </th>
                              <th className="text-left px-3 py-2 font-medium">
                                Message
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {workflow.results
                              .filter((r) => r.username)
                              .map((r, i) => (
                                <tr key={i} className="border-t">
                                  <td className="px-3 py-2 font-mono text-xs">
                                    {r.username}
                                  </td>
                                  <td className="px-3 py-2">
                                    {r.status === "success" ? (
                                      <span className="inline-flex items-center text-green-700">
                                        <CheckCircle className="h-3.5 w-3.5 mr-1" />
                                        Success
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center text-red-700">
                                        <XCircle className="h-3.5 w-3.5 mr-1" />
                                        Failed
                                      </span>
                                    )}
                                  </td>
                                  <td className="px-3 py-2 text-xs text-muted-foreground truncate max-w-xs">
                                    {r.message}
                                  </td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
