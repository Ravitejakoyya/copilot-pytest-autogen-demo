import { useState, useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, CheckCircle2, Clock, Play, XCircle, Loader2, Plus, GitBranch, Rocket, Activity, Layers, Shield } from "lucide-react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [pipelines, setPipelines] = useState([]);
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPipeline, setSelectedPipeline] = useState(null);
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [approvalComment, setApprovalComment] = useState("");
  const [selectedTab, setSelectedTab] = useState("overview");

  const fetchData = async () => {
    try {
      const [statsRes, pipelinesRes, appsRes] = await Promise.all([
        axios.get(`${API}/dashboard/stats`),
        axios.get(`${API}/pipelines`),
        axios.get(`${API}/applications`)
      ]);
      setStats(statsRes.data);
      setPipelines(pipelinesRes.data);
      setApplications(appsRes.data);
    } catch (e) {
      console.error(e);
      toast.error("Failed to fetch dashboard data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status) => {
    switch (status) {
      case "success":
        return <CheckCircle2 className="w-4 h-4 text-green-500" data-testid="success-icon" />;
      case "failed":
        return <XCircle className="w-4 h-4 text-red-500" data-testid="failed-icon" />;
      case "running":
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" data-testid="running-icon" />;
      case "waiting_approval":
        return <Clock className="w-4 h-4 text-yellow-500" data-testid="waiting-icon" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" data-testid="pending-icon" />;
    }
  };

  const getStatusBadge = (status) => {
    const variants = {
      success: "bg-green-500/10 text-green-600 border-green-500/20",
      failed: "bg-red-500/10 text-red-600 border-red-500/20",
      running: "bg-blue-500/10 text-blue-600 border-blue-500/20",
      waiting_approval: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
      pending: "bg-gray-500/10 text-gray-600 border-gray-500/20"
    };
    return (
      <Badge className={`${variants[status] || variants.pending} border`} data-testid={`status-badge-${status}`}>
        {status.replace("_", " ").toUpperCase()}
      </Badge>
    );
  };

  const handleApproval = async (approved) => {
    try {
      await axios.post(`${API}/pipelines/${selectedPipeline.id}/approve`, {
        approved,
        approved_by: "Resource Manager",
        comment: approvalComment
      });
      toast.success(`Pipeline ${approved ? 'approved' : 'rejected'} successfully`);
      setShowApprovalDialog(false);
      setApprovalComment("");
      fetchData();
    } catch (e) {
      toast.error(`Failed to ${approved ? 'approve' : 'reject'} pipeline`);
    }
  };

  const viewPipelineDetails = (pipeline) => {
    setSelectedPipeline(pipeline);
    setSelectedTab("details");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="dashboard">
      <Tabs value={selectedTab} onValueChange={setSelectedTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="overview" data-testid="overview-tab">Overview</TabsTrigger>
          <TabsTrigger value="details" data-testid="details-tab">Pipeline Details</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <Card data-testid="applications-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-gray-600">Applications</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{stats?.total_applications || 0}</div>
              </CardContent>
            </Card>

            <Card data-testid="pipelines-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-gray-600">Total Pipelines</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{stats?.total_pipelines || 0}</div>
              </CardContent>
            </Card>

            <Card data-testid="success-rate-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-gray-600">Success Rate</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-green-600">{stats?.success_rate || 0}%</div>
              </CardContent>
            </Card>

            <Card data-testid="today-pipelines-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-gray-600">Today</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{stats?.pipelines_today || 0}</div>
              </CardContent>
            </Card>

            <Card data-testid="pending-approvals-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-gray-600">Pending Approvals</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-yellow-600">{stats?.pending_approvals || 0}</div>
              </CardContent>
            </Card>
          </div>

          <Card data-testid="recent-pipelines-card">
            <CardHeader>
              <CardTitle>Recent Pipelines</CardTitle>
              <CardDescription>Latest pipeline executions across all applications</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {pipelines.slice(0, 10).map((pipeline) => (
                  <div
                    key={pipeline.id}
                    className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors cursor-pointer"
                    onClick={() => viewPipelineDetails(pipeline)}
                    data-testid={`pipeline-item-${pipeline.id}`}
                  >
                    <div className="flex items-center space-x-4">
                      {getStatusIcon(pipeline.status)}
                      <div>
                        <div className="font-semibold">{pipeline.application_name}</div>
                        <div className="text-sm text-gray-500">
                          {pipeline.environment} • {new Date(pipeline.created_at).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-3">
                      {getStatusBadge(pipeline.status)}
                      {pipeline.status === "waiting_approval" && (
                        <Button
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedPipeline(pipeline);
                            setShowApprovalDialog(true);
                          }}
                          data-testid={`approve-btn-${pipeline.id}`}
                        >
                          Review
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="details">
          {selectedPipeline ? (
            <Card data-testid="pipeline-details-card">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>{selectedPipeline.application_name}</CardTitle>
                    <CardDescription>
                      Pipeline ID: {selectedPipeline.id} • Environment: {selectedPipeline.environment.toUpperCase()}
                    </CardDescription>
                  </div>
                  {getStatusBadge(selectedPipeline.status)}
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm text-gray-500">Triggered By</div>
                      <div className="font-medium">{selectedPipeline.triggered_by}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-500">Started At</div>
                      <div className="font-medium">{new Date(selectedPipeline.created_at).toLocaleString()}</div>
                    </div>
                  </div>

                  <div>
                    <h3 className="font-semibold mb-4">Pipeline Stages</h3>
                    <div className="space-y-3">
                      {selectedPipeline.stages.map((stage, idx) => (
                        <div key={idx} className="flex items-center space-x-4" data-testid={`stage-${idx}`}>
                          <div className="flex-shrink-0">
                            {stage.status === "success" && <CheckCircle2 className="w-5 h-5 text-green-500" />}
                            {stage.status === "failed" && <XCircle className="w-5 h-5 text-red-500" />}
                            {stage.status === "running" && <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />}
                            {stage.status === "pending" && <Clock className="w-5 h-5 text-gray-400" />}
                          </div>
                          <div className="flex-1">
                            <div className="font-medium">{stage.name}</div>
                            {stage.duration_seconds && (
                              <div className="text-sm text-gray-500">Duration: {stage.duration_seconds}s</div>
                            )}
                          </div>
                          <Badge variant="outline">{stage.status}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="flex items-center justify-center h-64">
                <div className="text-center text-gray-500">
                  <Activity className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>Select a pipeline from the overview to view details</p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={showApprovalDialog} onOpenChange={setShowApprovalDialog}>
        <DialogContent data-testid="approval-dialog">
          <DialogHeader>
            <DialogTitle>Approve Pipeline Deployment</DialogTitle>
            <DialogDescription>
              Review and approve the production deployment for {selectedPipeline?.application_name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="approval-comment">Comment (Optional)</Label>
              <Textarea
                id="approval-comment"
                placeholder="Add approval notes..."
                value={approvalComment}
                onChange={(e) => setApprovalComment(e.target.value)}
                data-testid="approval-comment"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => handleApproval(false)} data-testid="reject-btn">
              Reject
            </Button>
            <Button onClick={() => handleApproval(true)} data-testid="approve-confirm-btn">
              Approve
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const Onboarding = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    tech_stack: [],
    build_tool: "",
    deployment_type: "",
    cloud_provider: "",
    cicd_tool: "",
    repository_url: "",
    branch: "main",
    security_checks: ["sonarqube", "trivy", "cycode"],
    notification_emails: "",
    resource_manager_email: ""
  });
  const [loading, setLoading] = useState(false);

  const techStackOptions = ["nodejs", "python", "java", "dotnet", "react", "angular", "vue"];
  const buildToolOptions = ["maven", "gradle", "npm", "yarn", "pip"];
  const deploymentTypeOptions = ["kubernetes", "docker", "vm", "serverless"];
  const cloudProviderOptions = ["aws", "azure", "gcp", "on-premise"];
  const cicdToolOptions = ["jenkins", "github_actions", "gitlab_ci"];
  const securityCheckOptions = ["sonarqube", "trivy", "cycode"];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const payload = {
        ...formData,
        notification_emails: formData.notification_emails.split(",").map(e => e.trim()).filter(e => e)
      };

      await axios.post(`${API}/applications`, payload);
      toast.success("Application onboarded successfully!");
      setTimeout(() => navigate("/trigger"), 1500);
    } catch (e) {
      console.error(e);
      toast.error("Failed to onboard application");
    } finally {
      setLoading(false);
    }
  };

  const toggleTechStack = (tech) => {
    setFormData(prev => ({
      ...prev,
      tech_stack: prev.tech_stack.includes(tech)
        ? prev.tech_stack.filter(t => t !== tech)
        : [...prev.tech_stack, tech]
    }));
  };

  const toggleSecurityCheck = (check) => {
    setFormData(prev => ({
      ...prev,
      security_checks: prev.security_checks.includes(check)
        ? prev.security_checks.filter(c => c !== check)
        : [...prev.security_checks, check]
    }));
  };

  return (
    <div data-testid="onboarding-form">
      <Card>
        <CardHeader>
          <CardTitle>Application Onboarding</CardTitle>
          <CardDescription>Register a new application for CI/CD orchestration</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Application Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  required
                  data-testid="app-name-input"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="repository_url">Repository URL *</Label>
                <Input
                  id="repository_url"
                  value={formData.repository_url}
                  onChange={(e) => setFormData({...formData, repository_url: e.target.value})}
                  placeholder="https://github.com/org/repo"
                  required
                  data-testid="repo-url-input"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description *</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({...formData, description: e.target.value})}
                required
                data-testid="description-input"
              />
            </div>

            <div className="space-y-2">
              <Label>Tech Stack *</Label>
              <div className="flex flex-wrap gap-2">
                {techStackOptions.map((tech) => (
                  <Button
                    key={tech}
                    type="button"
                    variant={formData.tech_stack.includes(tech) ? "default" : "outline"}
                    onClick={() => toggleTechStack(tech)}
                    data-testid={`tech-${tech}`}
                  >
                    {tech}
                  </Button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="build_tool">Build Tool *</Label>
                <Select value={formData.build_tool} onValueChange={(val) => setFormData({...formData, build_tool: val})}>
                  <SelectTrigger data-testid="build-tool-select">
                    <SelectValue placeholder="Select build tool" />
                  </SelectTrigger>
                  <SelectContent>
                    {buildToolOptions.map((tool) => (
                      <SelectItem key={tool} value={tool}>{tool}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="deployment_type">Deployment Type *</Label>
                <Select value={formData.deployment_type} onValueChange={(val) => setFormData({...formData, deployment_type: val})}>
                  <SelectTrigger data-testid="deployment-type-select">
                    <SelectValue placeholder="Select deployment type" />
                  </SelectTrigger>
                  <SelectContent>
                    {deploymentTypeOptions.map((type) => (
                      <SelectItem key={type} value={type}>{type}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="cloud_provider">Cloud Provider *</Label>
                <Select value={formData.cloud_provider} onValueChange={(val) => setFormData({...formData, cloud_provider: val})}>
                  <SelectTrigger data-testid="cloud-provider-select">
                    <SelectValue placeholder="Select cloud provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {cloudProviderOptions.map((provider) => (
                      <SelectItem key={provider} value={provider}>{provider}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="cicd_tool">CI/CD Tool *</Label>
                <Select value={formData.cicd_tool} onValueChange={(val) => setFormData({...formData, cicd_tool: val})}>
                  <SelectTrigger data-testid="cicd-tool-select">
                    <SelectValue placeholder="Select CI/CD tool" />
                  </SelectTrigger>
                  <SelectContent>
                    {cicdToolOptions.map((tool) => (
                      <SelectItem key={tool} value={tool}>{tool.replace("_", " ")}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Security Checks *</Label>
              <div className="flex flex-wrap gap-2">
                {securityCheckOptions.map((check) => (
                  <Button
                    key={check}
                    type="button"
                    variant={formData.security_checks.includes(check) ? "default" : "outline"}
                    onClick={() => toggleSecurityCheck(check)}
                    data-testid={`security-${check}`}
                  >
                    <Shield className="w-4 h-4 mr-2" />
                    {check}
                  </Button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="branch">Branch</Label>
                <Input
                  id="branch"
                  value={formData.branch}
                  onChange={(e) => setFormData({...formData, branch: e.target.value})}
                  data-testid="branch-input"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="resource_manager_email">Resource Manager Email *</Label>
                <Input
                  id="resource_manager_email"
                  type="email"
                  value={formData.resource_manager_email}
                  onChange={(e) => setFormData({...formData, resource_manager_email: e.target.value})}
                  required
                  data-testid="rm-email-input"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="notification_emails">Notification Emails (comma-separated) *</Label>
              <Input
                id="notification_emails"
                value={formData.notification_emails}
                onChange={(e) => setFormData({...formData, notification_emails: e.target.value})}
                placeholder="dev1@example.com, dev2@example.com"
                required
                data-testid="notification-emails-input"
              />
            </div>

            <Button type="submit" className="w-full" disabled={loading} data-testid="submit-onboarding-btn">
              {loading ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Onboarding...</>
              ) : (
                <><Plus className="w-4 h-4 mr-2" /> Onboard Application</>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

const PipelineTrigger = () => {
  const [applications, setApplications] = useState([]);
  const [selectedApp, setSelectedApp] = useState("");
  const [environment, setEnvironment] = useState("dev");
  const [triggeredBy, setTriggeredBy] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchApplications();
  }, []);

  const fetchApplications = async () => {
    try {
      const response = await axios.get(`${API}/applications`);
      setApplications(response.data);
    } catch (e) {
      console.error(e);
      toast.error("Failed to fetch applications");
    }
  };

  const handleTrigger = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await axios.post(`${API}/pipelines`, {
        application_id: selectedApp,
        environment,
        triggered_by: triggeredBy
      });

      const pipelineId = response.data.id;
      toast.success("Pipeline triggered successfully!");

      // Simulate pipeline execution
      await axios.post(`${API}/pipelines/${pipelineId}/simulate`);
      
      toast.info("Pipeline execution started");
      setTimeout(() => navigate("/"), 1500);
    } catch (e) {
      console.error(e);
      toast.error("Failed to trigger pipeline");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div data-testid="pipeline-trigger">
      <Card>
        <CardHeader>
          <CardTitle>Trigger Pipeline</CardTitle>
          <CardDescription>Start a new CI/CD pipeline execution</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleTrigger} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="application">Select Application *</Label>
              <Select value={selectedApp} onValueChange={setSelectedApp}>
                <SelectTrigger data-testid="app-select">
                  <SelectValue placeholder="Choose an application" />
                </SelectTrigger>
                <SelectContent>
                  {applications.map((app) => (
                    <SelectItem key={app.id} value={app.id}>
                      {app.name} ({app.tech_stack.join(", ")})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="environment">Environment *</Label>
              <Select value={environment} onValueChange={setEnvironment}>
                <SelectTrigger data-testid="env-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="dev">Development</SelectItem>
                  <SelectItem value="uat">UAT</SelectItem>
                  <SelectItem value="production">Production</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="triggered_by">Triggered By *</Label>
              <Input
                id="triggered_by"
                value={triggeredBy}
                onChange={(e) => setTriggeredBy(e.target.value)}
                placeholder="Enter your name or user ID"
                required
                data-testid="triggered-by-input"
              />
            </div>

            <Button type="submit" className="w-full" disabled={loading || !selectedApp} data-testid="trigger-pipeline-btn">
              {loading ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Triggering...</>
              ) : (
                <><Rocket className="w-4 h-4 mr-2" /> Trigger Pipeline</>
              )}
            </Button>
          </form>

          {applications.length === 0 && (
            <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-blue-800">
                No applications found. Please <Link to="/onboarding" className="underline font-semibold">onboard an application</Link> first.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

const Home = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <Toaster position="top-right" />
      <nav className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50" data-testid="navbar">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <Link to="/" className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                <Layers className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">CI/CD Orchestrator</h1>
                <p className="text-xs text-gray-500">Pipeline Automation Platform</p>
              </div>
            </Link>
            <div className="flex items-center space-x-2">
              <Link to="/">
                <Button variant="ghost" data-testid="nav-dashboard">
                  <Activity className="w-4 h-4 mr-2" />
                  Dashboard
                </Button>
              </Link>
              <Link to="/onboarding">
                <Button variant="ghost" data-testid="nav-onboarding">
                  <Plus className="w-4 h-4 mr-2" />
                  Onboarding
                </Button>
              </Link>
              <Link to="/trigger">
                <Button variant="ghost" data-testid="nav-trigger">
                  <Rocket className="w-4 h-4 mr-2" />
                  Trigger
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </nav>

      <main className="container mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/trigger" element={<PipelineTrigger />} />
        </Routes>
      </main>
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    </div>
  );
}

export default App;
