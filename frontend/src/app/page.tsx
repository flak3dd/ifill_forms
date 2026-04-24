"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import WorkflowWizard from "@/components/WorkflowWizard";
import { 
  PlayCircle, 
  PauseCircle, 
  StopCircle, 
  Upload, 
  Settings, 
  BarChart3, 
  Zap,
  Globe,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  Plus,
  Workflow,
  Trash2,
  ExternalLink,
} from "lucide-react";

interface Job {
  id: string;
  name: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  total_rows: number;
  processed_rows: number;
  successful_rows: number;
  failed_rows: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface Profile {
  id: string;
  name: string;
  description?: string;
  base_url: string;
  is_active: boolean;
  created_at: string;
}

interface AutomationWorkflow {
  id: string;
  name: string;
  target_url: string;
  status: string;
  credential_count: number;
  total_credentials: number;
  processed_count: number;
  successful_count: number;
  failed_count: number;
  detected_fields: Record<string, any>;
  created_at: string;
  updated_at: string;
}

type View = "dashboard" | "new-workflow";

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [workflows, setWorkflows] = useState<AutomationWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<View>("dashboard");

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [jobsResponse, profilesResponse, workflowsResponse] = await Promise.all([
        fetch("/api/jobs"),
        fetch("/api/profiles"),
        fetch("/api/workflows/"),
      ]);

      const jobsData = await jobsResponse.json();
      const profilesData = await profilesResponse.json();
      const workflowsData = workflowsResponse.ok ? await workflowsResponse.json() : [];

      setJobs(jobsData);
      setProfiles(profilesData);
      setWorkflows(Array.isArray(workflowsData) ? workflowsData : []);
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
    } finally {
      setLoading(false);
    }
  };

  const deleteWorkflow = async (id: string) => {
    if (!confirm("Delete this workflow?")) return;
    await fetch(`/api/workflows/${id}`, { method: "DELETE" });
    setWorkflows((prev) => prev.filter((w) => w.id !== id));
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "running":
        return <PlayCircle className="h-4 w-4 text-blue-500" />;
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "cancelled":
      case "stopped":
        return <StopCircle className="h-4 w-4 text-gray-500" />;
      default:
        return <Clock className="h-4 w-4 text-yellow-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running":
        return "bg-blue-100 text-blue-800";
      case "completed":
        return "bg-green-100 text-green-800";
      case "failed":
        return "bg-red-100 text-red-800";
      case "cancelled":
      case "stopped":
        return "bg-gray-100 text-gray-800";
      case "ready":
        return "bg-indigo-100 text-indigo-800";
      default:
        return "bg-yellow-100 text-yellow-800";
    }
  };

  const getProgressPercentage = (job: Job) => {
    return job.total_rows > 0 ? (job.processed_rows / job.total_rows) * 100 : 0;
  };

  const getSuccessRate = (job: Job) => {
    return job.processed_rows > 0 ? (job.successful_rows / job.processed_rows) * 100 : 0;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary"></div>
      </div>
    );
  }

  // ── Workflow Wizard view ──
  if (view === "new-workflow") {
    return (
      <div className="container mx-auto p-6">
        <WorkflowWizard
          onBack={() => {
            setView("dashboard");
            fetchDashboardData();
          }}
        />
      </div>
    );
  }

  // ── Dashboard view ──
  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">FormForge AI Dashboard</h1>
          <p className="text-muted-foreground">
            Intelligent web form automation engine
          </p>
        </div>
        <div className="flex space-x-2">
          <Button onClick={() => setView("new-workflow")}>
            <Plus className="mr-2 h-4 w-4" />
            New Workflow
          </Button>
          <Button variant="outline">
            <Settings className="mr-2 h-4 w-4" />
            Settings
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Workflows</CardTitle>
            <Workflow className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{workflows.length}</div>
            <p className="text-xs text-muted-foreground">
              {workflows.filter(w => w.status === "running").length} running
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Logins Attempted</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {workflows.reduce((acc, w) => acc + w.processed_count, 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              across all workflows
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(() => {
                const total = workflows.reduce((a, w) => a + w.processed_count, 0);
                const success = workflows.reduce((a, w) => a + w.successful_count, 0);
                return total > 0 ? Math.round((success / total) * 100) : 0;
              })()}%
            </div>
            <p className="text-xs text-muted-foreground">
              overall
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Successful Logins</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {workflows.reduce((acc, w) => acc + w.successful_count, 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              {workflows.reduce((acc, w) => acc + w.failed_count, 0)} failed
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <Tabs defaultValue="workflows" className="space-y-4">
        <TabsList>
          <TabsTrigger value="workflows">Workflows</TabsTrigger>
          <TabsTrigger value="jobs">Jobs</TabsTrigger>
          <TabsTrigger value="profiles">Profiles</TabsTrigger>
        </TabsList>

        {/* ── Workflows Tab ── */}
        <TabsContent value="workflows" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Automation Workflows</CardTitle>
                  <CardDescription>
                    Login automation workflows - scan, upload credentials, run
                  </CardDescription>
                </div>
                <Button size="sm" onClick={() => setView("new-workflow")}>
                  <Plus className="h-4 w-4 mr-1" /> New
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {workflows.length === 0 ? (
                  <div className="text-center py-8">
                    <Globe className="mx-auto h-12 w-12 text-muted-foreground" />
                    <h3 className="mt-2 text-sm font-semibold">No workflows yet</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Create a workflow to start automating logins.
                    </p>
                    <div className="mt-6">
                      <Button onClick={() => setView("new-workflow")}>
                        <Plus className="h-4 w-4 mr-2" /> Create Workflow
                      </Button>
                    </div>
                  </div>
                ) : (
                  workflows.map((wf) => (
                    <div key={wf.id} className="border rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          {getStatusIcon(wf.status)}
                          <div>
                            <h4 className="font-medium">{wf.name}</h4>
                            <p className="text-sm text-muted-foreground flex items-center space-x-1">
                              <ExternalLink className="h-3 w-3" />
                              <span className="truncate max-w-xs">{wf.target_url}</span>
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Badge className={getStatusColor(wf.status)}>
                            {wf.status}
                          </Badge>
                          {wf.credential_count > 0 && (
                            <Badge variant="outline">
                              {wf.credential_count} creds
                            </Badge>
                          )}
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => deleteWorkflow(wf.id)}
                          >
                            <Trash2 className="h-4 w-4 text-muted-foreground" />
                          </Button>
                        </div>
                      </div>

                      {/* Progress if has results */}
                      {wf.total_credentials > 0 && wf.processed_count > 0 && (
                        <>
                          <div className="space-y-2">
                            <div className="flex justify-between text-sm">
                              <span>
                                Progress: {wf.processed_count} / {wf.total_credentials}
                              </span>
                              <span>
                                {Math.round(
                                  (wf.processed_count / wf.total_credentials) * 100
                                )}%
                              </span>
                            </div>
                            <Progress
                              value={
                                (wf.processed_count / wf.total_credentials) * 100
                              }
                            />
                          </div>
                          <div className="grid grid-cols-3 gap-4 text-sm">
                            <div>
                              <span className="text-muted-foreground">Successful:</span>
                              <span className="ml-2 font-medium text-green-600">
                                {wf.successful_count}
                              </span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">Failed:</span>
                              <span className="ml-2 font-medium text-red-600">
                                {wf.failed_count}
                              </span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">Confidence:</span>
                              <span className="ml-2 font-medium">
                                {Math.round(
                                  (wf.detected_fields?.confidence || 0) * 100
                                )}%
                              </span>
                            </div>
                          </div>
                        </>
                      )}

                      <p className="text-xs text-muted-foreground">
                        Created {new Date(wf.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Jobs Tab ── */}
        <TabsContent value="jobs" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Jobs</CardTitle>
              <CardDescription>
                Monitor and manage your automation jobs
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {jobs.length === 0 ? (
                  <div className="text-center py-8">
                    <FileText className="mx-auto h-12 w-12 text-muted-foreground" />
                    <h3 className="mt-2 text-sm font-semibold">No jobs yet</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Get started by creating your first automation job.
                    </p>
                  </div>
                ) : (
                  jobs.map((job) => (
                    <div key={job.id} className="border rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          {getStatusIcon(job.status)}
                          <div>
                            <h4 className="font-medium">{job.name}</h4>
                            <p className="text-sm text-muted-foreground">
                              Created {new Date(job.created_at).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Badge className={getStatusColor(job.status)}>
                            {job.status}
                          </Badge>
                          {job.status === "running" && (
                            <Button size="sm" variant="outline">
                              <StopCircle className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span>Progress: {job.processed_rows} / {job.total_rows}</span>
                          <span>{Math.round(getProgressPercentage(job))}%</span>
                        </div>
                        <Progress value={getProgressPercentage(job)} />
                      </div>

                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <span className="text-muted-foreground">Successful:</span>
                          <span className="ml-2 font-medium text-green-600">
                            {job.successful_rows}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Failed:</span>
                          <span className="ml-2 font-medium text-red-600">
                            {job.failed_rows}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Success Rate:</span>
                          <span className="ml-2 font-medium">
                            {Math.round(getSuccessRate(job))}%
                          </span>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Profiles Tab ── */}
        <TabsContent value="profiles" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Site Profiles</CardTitle>
              <CardDescription>
                Manage your website automation profiles
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {profiles.length === 0 ? (
                  <div className="text-center py-8">
                    <Globe className="mx-auto h-12 w-12 text-muted-foreground" />
                    <h3 className="mt-2 text-sm font-semibold">No profiles yet</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Create a profile to start automating web forms.
                    </p>
                    <div className="mt-6">
                      <Button>Create Profile</Button>
                    </div>
                  </div>
                ) : (
                  profiles.map((profile) => (
                    <div key={profile.id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-medium">{profile.name}</h4>
                          <p className="text-sm text-muted-foreground">
                            {profile.description || profile.base_url}
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            Created {new Date(profile.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Badge variant={profile.is_active ? "default" : "secondary"}>
                            {profile.is_active ? "Active" : "Inactive"}
                          </Badge>
                          <Button size="sm" variant="outline">
                            <Settings className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
