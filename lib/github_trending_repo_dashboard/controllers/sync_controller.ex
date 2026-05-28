defmodule GitHubTrendingRepoDashboard.SyncController do
  use Phoenix.Controller, formats: [:json]

  @github_api "https://api.github.com"

  def create(conn, _params) do
    case verify_sync_secret(conn) do
      :ok ->
        repo = System.get_env("GITHUB_REPO") || "maximoseo/GitHub-Trending-Repo-Dashboard"

        case github_token() do
          {:error, :missing_github_token} ->
            conn |> put_status(503) |> json(%{error: "GITHUB_TOKEN not configured"})

          {:ok, _token} ->
            case dispatch_workflow(repo) do
              {:ok, run_id} ->
                json(conn, %{status: "dispatched", run_id: run_id})

              {:error, reason} ->
                conn
                |> put_status(502)
                |> json(%{error: "Workflow dispatch failed", detail: inspect(reason)})
            end
        end

      {:error, :unauthorized} ->
        conn |> put_status(401) |> json(%{error: "Unauthorized"})
    end
  end

  def status(conn, _params) do
    case github_token() do
      {:error, :missing_github_token} ->
        conn |> put_status(503) |> json(%{error: "GITHUB_TOKEN not configured"})

      {:ok, _} ->
        status_workflow(conn)
    end
  end

  defp status_workflow(conn) do
    repo = System.get_env("GITHUB_REPO") || "maximoseo/GitHub-Trending-Repo-Dashboard"

    case latest_workflow_run(repo) do
      {:ok, payload} -> json(conn, payload)
      {:error, reason} -> conn |> put_status(502) |> json(%{error: inspect(reason)})
    end
  end

  # Dashboard UI calls POST /api/sync without a secret. When SYNC_SECRET is set,
  # only reject requests that send a wrong x-sync-secret header (optional hardening for curl).
  defp verify_sync_secret(conn) do
    expected = System.get_env("SYNC_SECRET")

    if is_nil(expected) or expected == "" do
      :ok
    else
      case get_req_header(conn, "x-sync-secret") do
        [] -> :ok
        [^expected] -> :ok
        _ -> {:error, :unauthorized}
      end
    end
  end

  defp dispatch_workflow(repo) do
    [owner, name] = String.split(repo, "/", parts: 2)
    url = "#{@github_api}/repos/#{owner}/#{name}/actions/workflows/sync-sources.yml/dispatches"
    body = Jason.encode!(%{ref: "main"})

    case Finch.build(:post, url, github_headers(), body)
         |> Finch.request(GitHubTrendingRepoDashboard.Finch) do
      {:ok, %{status: status}} when status in [200, 204] ->
        case latest_workflow_run(repo) do
          {:ok, %{run_id: run_id}} -> {:ok, run_id}
          _ -> {:ok, nil}
        end

      other ->
        {:error, other}
    end
  end

  defp latest_workflow_run(repo) do
    [owner, name] = String.split(repo, "/", parts: 2)

    url =
      "#{@github_api}/repos/#{owner}/#{name}/actions/workflows/sync-sources.yml/runs?per_page=1"

    case Finch.build(:get, url, github_headers()) |> Finch.request(GitHubTrendingRepoDashboard.Finch) do
      {:ok, %{status: 200, body: body}} ->
        data = Jason.decode!(body)
        run = List.first(data["workflow_runs"] || [])

        if run do
          {:ok,
           %{
             run_id: run["id"],
             status: run["status"],
             conclusion: run["conclusion"],
             html_url: run["html_url"],
             created_at: run["created_at"],
             updated_at: run["updated_at"]
           }}
        else
          {:ok, %{status: "idle", run_id: nil}}
        end

      other ->
        {:error, other}
    end
  end

  defp github_token do
    case System.get_env("GITHUB_TOKEN") do
      token when is_binary(token) and token != "" -> {:ok, token}
      _ -> {:error, :missing_github_token}
    end
  end

  defp github_headers do
    {:ok, token} = github_token()

    [
      {"authorization", "Bearer #{token}"},
      {"accept", "application/vnd.github+json"},
      {"user-agent", "github-trending-repo-dashboard"}
    ]
  end
end
