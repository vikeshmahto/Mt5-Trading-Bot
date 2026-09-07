module.exports = {
  apps: [
    {
      name: "live-runner",
      script: "execution/live_runner.py",
      interpreter: "python",
      args: "--env paper",
      watch: false,
      max_restarts: 10,
      restart_delay: 5000,
      error_file: "logs/pm2-live-runner-error.log",
      out_file: "logs/pm2-live-runner-out.log",
      time: true
    },
    {
      name: "dashboard-backend",
      script: "uvicorn",
      interpreter: "python",
      args: "backend.app.main:app --host 0.0.0.0 --port 8000 --reload",
      watch: false,
      max_restarts: 10,
      restart_delay: 5000,
      error_file: "logs/pm2-dashboard-error.log",
      out_file: "logs/pm2-dashboard-out.log",
      time: true
    }
  ]
};
