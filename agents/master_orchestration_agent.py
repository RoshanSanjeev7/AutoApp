"""
Master Orchestration Agent - Coordinates all autonomous agents and schedules tasks
"""
import os
import json
import time
import asyncio
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import schedule
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.logger import setup_logger
from agents.autonomous_job_search_agent import AutonomousJobSearchAgent
from agents.learning_adaptation_agent import LearningAdaptationAgent
from agents.autonomous_application_agent import AutonomousApplicationAgent


class MasterOrchestrationAgent:
    """Master agent that coordinates all autonomous job application activities"""
    
    def __init__(self):
        self.logger = setup_logger("master_orchestration")
        
        # Initialize sub-agents
        self.job_search_agent = AutonomousJobSearchAgent()
        self.learning_agent = LearningAdaptationAgent()
        self.application_agent = AutonomousApplicationAgent()
        
        # Load orchestration configuration
        self.config = self._load_orchestration_config()
        
        # Agent state and monitoring
        self.agent_states = {
            "job_search": {"status": "idle", "last_run": None, "next_run": None},
            "learning": {"status": "idle", "last_run": None, "next_run": None},
            "application": {"status": "idle", "last_run": None, "next_run": None},
            "orchestration": {"status": "active", "started_at": datetime.now().isoformat()}
        }
        
        # Performance tracking
        self.performance_history = self._load_performance_history()
        
        # Scheduler for autonomous operations
        self.scheduler_running = False
        self.scheduler_thread = None
        
        # Feedback loop monitoring
        self.feedback_monitors = {
            "email_monitor": None,
            "application_tracker": None,
            "response_detector": None
        }
        
    def _load_orchestration_config(self) -> Dict[str, Any]:
        """Load orchestration configuration"""
        config_file = "data/orchestration_config.json"
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load orchestration config: {e}")
        
        # Default configuration
        default_config = {
            "autonomous_mode": False,  # Start disabled for safety
            "scheduling": {
                "job_search_frequency": "daily",  # hourly, daily, weekly
                "job_search_time": "09:00",
                "application_processing_frequency": "every_4_hours",
                "learning_update_frequency": "daily",
                "performance_review_frequency": "weekly"
            },
            "workflow": {
                "max_concurrent_agents": 2,
                "agent_timeout_minutes": 30,
                "retry_failed_tasks": True,
                "max_retries": 3,
                "cooldown_between_cycles": 3600  # 1 hour
            },
            "quality_control": {
                "min_job_score_threshold": 0.7,
                "max_applications_per_cycle": 5,
                "require_human_approval": True,
                "auto_pause_on_errors": True,
                "error_threshold": 5
            },
            "monitoring": {
                "track_agent_performance": True,
                "log_all_activities": True,
                "send_daily_reports": False,
                "alert_on_failures": True
            },
            "optimization": {
                "auto_adjust_schedules": True,
                "learn_from_outcomes": True,
                "optimize_timing": True,
                "adapt_search_criteria": True
            }
        }
        
        # Save default config
        os.makedirs("data", exist_ok=True)
        try:
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            self.logger.info("Default orchestration config created")
        except Exception as e:
            self.logger.warning(f"Could not save default config: {e}")
        
        return default_config
    
    def _load_performance_history(self) -> List[Dict[str, Any]]:
        """Load historical performance data"""
        history_file = "data/orchestration_performance.json"
        
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load performance history: {e}")
        
        return []
    
    def start_autonomous_operation(self):
        """Start autonomous job application operations"""
        if not self.config.get('autonomous_mode', False):
            self.logger.warning("Autonomous mode is disabled")
            return {"status": "disabled", "message": "Autonomous mode is disabled in configuration"}
        
        if self.scheduler_running:
            self.logger.warning("Autonomous operation already running")
            return {"status": "already_running", "message": "Autonomous operation is already active"}
        
        self.logger.info("Starting autonomous job application operation...")
        
        # Setup scheduled tasks
        self._setup_scheduled_tasks()
        
        # Start scheduler in separate thread
        self.scheduler_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        # Initialize feedback monitoring
        self._start_feedback_monitoring()
        
        # Update agent state
        self.agent_states["orchestration"]["status"] = "autonomous"
        self.agent_states["orchestration"]["autonomous_started"] = datetime.now().isoformat()
        
        self.logger.info("Autonomous operation started successfully")
        
        return {
            "status": "started",
            "message": "Autonomous job application operation is now active",
            "config": self.config["scheduling"],
            "next_scheduled_tasks": self._get_next_scheduled_tasks()
        }
    
    def stop_autonomous_operation(self):
        """Stop autonomous operations"""
        self.logger.info("Stopping autonomous operation...")
        
        self.scheduler_running = False
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        # Stop feedback monitoring
        self._stop_feedback_monitoring()
        
        # Update agent state
        self.agent_states["orchestration"]["status"] = "manual"
        self.agent_states["orchestration"]["autonomous_stopped"] = datetime.now().isoformat()
        
        # Clear scheduled tasks
        schedule.clear()
        
        self.logger.info("Autonomous operation stopped")
        
        return {"status": "stopped", "message": "Autonomous operation has been stopped"}
    
    def _setup_scheduled_tasks(self):
        """Setup scheduled tasks based on configuration"""
        scheduling_config = self.config.get('scheduling', {})
        
        # Job search scheduling
        search_frequency = scheduling_config.get('job_search_frequency', 'daily')
        search_time = scheduling_config.get('job_search_time', '09:00')
        
        if search_frequency == 'hourly':
            schedule.every().hour.do(self._run_job_search_cycle)
        elif search_frequency == 'daily':
            schedule.every().day.at(search_time).do(self._run_job_search_cycle)
        elif search_frequency == 'weekly':
            schedule.every().week.at(search_time).do(self._run_job_search_cycle)
        
        # Application processing scheduling
        app_frequency = scheduling_config.get('application_processing_frequency', 'every_4_hours')
        if app_frequency == 'every_4_hours':
            schedule.every(4).hours.do(self._run_application_cycle)
        elif app_frequency == 'every_2_hours':
            schedule.every(2).hours.do(self._run_application_cycle)
        elif app_frequency == 'hourly':
            schedule.every().hour.do(self._run_application_cycle)
        
        # Learning and optimization
        learning_frequency = scheduling_config.get('learning_update_frequency', 'daily')
        if learning_frequency == 'daily':
            schedule.every().day.at("18:00").do(self._run_learning_cycle)
        elif learning_frequency == 'weekly':
            schedule.every().week.do(self._run_learning_cycle)
        
        # Performance review
        review_frequency = scheduling_config.get('performance_review_frequency', 'weekly')
        if review_frequency == 'weekly':
            schedule.every().sunday.at("20:00").do(self._run_performance_review)
        elif review_frequency == 'daily':
            schedule.every().day.at("20:00").do(self._run_performance_review)
        
        self.logger.info("Scheduled tasks configured successfully")
    
    def _run_scheduler(self):
        """Run the task scheduler"""
        self.logger.info("Scheduler thread started")
        
        while self.scheduler_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                self.logger.error(f"Scheduler error: {e}")
                time.sleep(60)
        
        self.logger.info("Scheduler thread stopped")
    
    def _run_job_search_cycle(self):
        """Execute a job search cycle"""
        if not self._should_run_agent("job_search"):
            return
        
        self.logger.info("Starting scheduled job search cycle")
        
        try:
            self.agent_states["job_search"]["status"] = "running"
            self.agent_states["job_search"]["last_run"] = datetime.now().isoformat()
            
            # Run job search
            jobs_found = self.job_search_agent.search_jobs_autonomously()
            
            # Add high-quality jobs to application queue
            high_quality_jobs = [job for job in jobs_found if job.get('score', 0) >= self.config.get('quality_control', {}).get('min_job_score_threshold', 0.7)]
            
            applications_queued = 0
            for job in high_quality_jobs:
                application_id = self.application_agent.add_to_application_queue(job, priority="normal")
                if application_id:
                    applications_queued += 1
            
            # Update state
            self.agent_states["job_search"]["status"] = "completed"
            self.agent_states["job_search"]["jobs_found"] = len(jobs_found)
            self.agent_states["job_search"]["applications_queued"] = applications_queued
            
            # Record performance
            self._record_cycle_performance("job_search", {
                "jobs_found": len(jobs_found),
                "high_quality_jobs": len(high_quality_jobs),
                "applications_queued": applications_queued
            })
            
            self.logger.info(f"Job search cycle completed: {len(jobs_found)} jobs found, {applications_queued} queued for application")
            
        except Exception as e:
            self.logger.error(f"Job search cycle failed: {e}")
            self.agent_states["job_search"]["status"] = "failed"
            self.agent_states["job_search"]["error"] = str(e)
            
            self._handle_agent_failure("job_search", e)
    
    def _run_application_cycle(self):
        """Execute an application processing cycle"""
        if not self._should_run_agent("application"):
            return
        
        self.logger.info("Starting scheduled application cycle")
        
        try:
            self.agent_states["application"]["status"] = "running"
            self.agent_states["application"]["last_run"] = datetime.now().isoformat()
            
            # Process application queue
            results = self.application_agent.process_application_queue()
            
            # Update state
            self.agent_states["application"]["status"] = "completed"
            self.agent_states["application"]["last_results"] = results
            
            # Record performance
            self._record_cycle_performance("application", results)
            
            self.logger.info(f"Application cycle completed: {results.get('successful', 0)} successful, {results.get('failed', 0)} failed")
            
        except Exception as e:
            self.logger.error(f"Application cycle failed: {e}")
            self.agent_states["application"]["status"] = "failed"
            self.agent_states["application"]["error"] = str(e)
            
            self._handle_agent_failure("application", e)
    
    def _run_learning_cycle(self):
        """Execute a learning and optimization cycle"""
        if not self._should_run_agent("learning"):
            return
        
        self.logger.info("Starting scheduled learning cycle")
        
        try:
            self.agent_states["learning"]["status"] = "running"
            self.agent_states["learning"]["last_run"] = datetime.now().isoformat()
            
            # Get optimization recommendations
            recommendations = self.learning_agent.get_optimization_recommendations()
            
            # Apply optimizations if enabled
            if self.config.get('optimization', {}).get('auto_adjust_schedules', True):
                self._apply_timing_optimizations(recommendations.get('timing_recommendations', {}))
            
            if self.config.get('optimization', {}).get('adapt_search_criteria', True):
                self._apply_search_optimizations(recommendations.get('skill_recommendations', {}))
            
            # Update state
            self.agent_states["learning"]["status"] = "completed"
            self.agent_states["learning"]["last_recommendations"] = recommendations
            
            # Record performance
            self._record_cycle_performance("learning", {
                "recommendations_generated": len(recommendations),
                "optimizations_applied": True
            })
            
            self.logger.info("Learning cycle completed successfully")
            
        except Exception as e:
            self.logger.error(f"Learning cycle failed: {e}")
            self.agent_states["learning"]["status"] = "failed"
            self.agent_states["learning"]["error"] = str(e)
            
            self._handle_agent_failure("learning", e)
    
    def _run_performance_review(self):
        """Execute a comprehensive performance review"""
        self.logger.info("Starting performance review")
        
        try:
            # Gather performance data from all agents
            search_analytics = self.job_search_agent.get_search_analytics()
            learning_recommendations = self.learning_agent.get_optimization_recommendations()
            queue_status = self.application_agent.get_queue_status()
            
            # Generate comprehensive report
            performance_report = {
                "timestamp": datetime.now().isoformat(),
                "period": "weekly",
                "search_performance": search_analytics,
                "learning_insights": learning_recommendations,
                "application_status": queue_status,
                "orchestration_stats": self._get_orchestration_stats(),
                "recommendations": self._generate_system_recommendations(search_analytics, learning_recommendations, queue_status)
            }
            
            # Save performance report
            self._save_performance_report(performance_report)
            
            # Auto-optimize if enabled
            if self.config.get('optimization', {}).get('auto_adjust_schedules', True):
                self._auto_optimize_system(performance_report)
            
            self.logger.info("Performance review completed")
            
        except Exception as e:
            self.logger.error(f"Performance review failed: {e}")
    
    def _should_run_agent(self, agent_name: str) -> bool:
        """Check if an agent should run based on current conditions"""
        agent_state = self.agent_states.get(agent_name, {})
        
        # Check if agent is already running
        if agent_state.get("status") == "running":
            self.logger.warning(f"Agent {agent_name} is already running")
            return False
        
        # Check error threshold
        quality_config = self.config.get('quality_control', {})
        if quality_config.get('auto_pause_on_errors', True):
            recent_errors = self._count_recent_errors(agent_name)
            error_threshold = quality_config.get('error_threshold', 5)
            
            if recent_errors >= error_threshold:
                self.logger.warning(f"Agent {agent_name} has too many recent errors ({recent_errors}), skipping run")
                return False
        
        return True
    
    def _handle_agent_failure(self, agent_name: str, error: Exception):
        """Handle agent failure with retry logic and error handling"""
        workflow_config = self.config.get('workflow', {})
        
        # Record error
        error_record = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "error": str(error),
            "error_type": type(error).__name__
        }
        
        self._record_error(error_record)
        
        # Check if we should retry
        if workflow_config.get('retry_failed_tasks', True):
            max_retries = workflow_config.get('max_retries', 3)
            
            # Implement retry logic here if needed
            self.logger.info(f"Agent {agent_name} failed, retry logic can be implemented")
        
        # Check if we should pause autonomous operation
        quality_config = self.config.get('quality_control', {})
        if quality_config.get('auto_pause_on_errors', True):
            recent_errors = self._count_recent_errors(agent_name)
            error_threshold = quality_config.get('error_threshold', 5)
            
            if recent_errors >= error_threshold:
                self.logger.critical(f"Too many errors in {agent_name}, pausing autonomous operation")
                self.stop_autonomous_operation()
    
    def _apply_timing_optimizations(self, timing_recommendations: Dict[str, Any]):
        """Apply timing optimizations based on learning"""
        try:
            optimal_hours = timing_recommendations.get('optimal_application_hours', [])
            optimal_days = timing_recommendations.get('optimal_application_days', [])
            
            if optimal_hours and self.config.get('optimization', {}).get('optimize_timing', True):
                # Find the best hour and update application processing schedule
                best_hour = max(optimal_hours, key=lambda x: x['success_rate'])['hour']
                
                # Update scheduling configuration
                schedule.clear('application')  # Clear existing application schedules
                
                # Reschedule based on optimal timing
                schedule.every().day.at(f"{best_hour:02d}:00").do(self._run_application_cycle).tag('application')
                
                self.logger.info(f"Optimized application timing to {best_hour}:00 based on success rate")
                
        except Exception as e:
            self.logger.error(f"Error applying timing optimizations: {e}")
    
    def _apply_search_optimizations(self, skill_recommendations: Dict[str, Any]):
        """Apply search optimizations based on learning"""
        try:
            top_skills = skill_recommendations.get('top_performing_skills', [])
            emerging_skills = skill_recommendations.get('emerging_skills', [])
            
            if top_skills or emerging_skills:
                # Update job search agent preferences
                new_skills = [skill['skill'] for skill in top_skills] + emerging_skills
                
                # This would update the search preferences
                current_prefs = self.job_search_agent.preferences
                current_prefs['preferred_skills'].extend(new_skills)
                
                # Remove duplicates and limit size
                current_prefs['preferred_skills'] = list(set(current_prefs['preferred_skills']))[-20:]
                
                self.job_search_agent._save_search_preferences()
                
                self.logger.info(f"Updated search preferences with {len(new_skills)} optimized skills")
                
        except Exception as e:
            self.logger.error(f"Error applying search optimizations: {e}")
    
    def _start_feedback_monitoring(self):
        """Start monitoring for application feedback"""
        if self.config.get('monitoring', {}).get('track_agent_performance', True):
            # This could be enhanced with email monitoring, status checking, etc.
            self.logger.info("Feedback monitoring initialized")
    
    def _stop_feedback_monitoring(self):
        """Stop feedback monitoring"""
        self.logger.info("Feedback monitoring stopped")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "orchestration": {
                "autonomous_mode": self.config.get('autonomous_mode', False),
                "scheduler_running": self.scheduler_running,
                "agent_states": self.agent_states,
                "next_scheduled_tasks": self._get_next_scheduled_tasks()
            },
            "agents": {
                "job_search": self.job_search_agent.get_search_analytics(),
                "learning": self.learning_agent.get_optimization_recommendations(),
                "application": self.application_agent.get_queue_status()
            },
            "performance": {
                "recent_performance": self.performance_history[-10:] if self.performance_history else [],
                "system_health": self._assess_system_health()
            },
            "configuration": self.config
        }
    
    def execute_manual_cycle(self, cycle_type: str = "full") -> Dict[str, Any]:
        """Manually execute a complete cycle"""
        self.logger.info(f"Starting manual {cycle_type} cycle")
        
        results = {
            "cycle_type": cycle_type,
            "started_at": datetime.now().isoformat(),
            "steps": []
        }
        
        try:
            if cycle_type in ["full", "search"]:
                # Job search
                self.logger.info("Step 1: Searching for jobs")
                jobs_found = self.job_search_agent.search_jobs_autonomously()
                
                # Queue applications
                applications_queued = 0
                for job in jobs_found:
                    if job.get('score', 0) >= 0.7:  # Quality threshold
                        app_id = self.application_agent.add_to_application_queue(job)
                        if app_id:
                            applications_queued += 1
                
                results["steps"].append({
                    "step": "job_search",
                    "status": "completed",
                    "jobs_found": len(jobs_found),
                    "applications_queued": applications_queued
                })
            
            if cycle_type in ["full", "apply"]:
                # Process applications
                self.logger.info("Step 2: Processing applications")
                app_results = self.application_agent.process_application_queue()
                
                results["steps"].append({
                    "step": "application_processing",
                    "status": "completed",
                    "results": app_results
                })
            
            if cycle_type in ["full", "learn"]:
                # Learning update
                self.logger.info("Step 3: Updating learning models")
                recommendations = self.learning_agent.get_optimization_recommendations()
                
                results["steps"].append({
                    "step": "learning_update",
                    "status": "completed",
                    "recommendations": recommendations
                })
            
            results["status"] = "completed"
            results["completed_at"] = datetime.now().isoformat()
            
        except Exception as e:
            self.logger.error(f"Manual cycle failed: {e}")
            results["status"] = "failed"
            results["error"] = str(e)
            results["failed_at"] = datetime.now().isoformat()
        
        return results
    
    # Helper methods
    def _get_next_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Get next scheduled tasks"""
        next_tasks = []
        
        for job in schedule.jobs:
            next_tasks.append({
                "task": str(job.job_func.__name__),
                "next_run": job.next_run.isoformat() if job.next_run else None,
                "frequency": str(job.interval)
            })
        
        return sorted(next_tasks, key=lambda x: x['next_run'] or '9999-01-01')
    
    def _record_cycle_performance(self, agent_name: str, performance_data: Dict[str, Any]):
        """Record performance data for a cycle"""
        performance_record = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "performance": performance_data,
            "cycle_type": "scheduled"
        }
        
        self.performance_history.append(performance_record)
        
        # Keep only last 1000 records
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]
        
        self._save_performance_history()
    
    def _record_error(self, error_record: Dict[str, Any]):
        """Record error information"""
        errors_file = "data/orchestration_errors.json"
        
        try:
            if os.path.exists(errors_file):
                with open(errors_file, 'r') as f:
                    errors = json.load(f)
            else:
                errors = []
            
            errors.append(error_record)
            
            # Keep only last 500 errors
            if len(errors) > 500:
                errors = errors[-500:]
            
            with open(errors_file, 'w') as f:
                json.dump(errors, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error recording error: {e}")
    
    def _count_recent_errors(self, agent_name: str, hours: int = 24) -> int:
        """Count recent errors for an agent"""
        errors_file = "data/orchestration_errors.json"
        
        if not os.path.exists(errors_file):
            return 0
        
        try:
            with open(errors_file, 'r') as f:
                errors = json.load(f)
            
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_errors = 0
            
            for error in errors:
                if error.get('agent') == agent_name:
                    error_time = datetime.fromisoformat(error['timestamp'])
                    if error_time > cutoff_time:
                        recent_errors += 1
            
            return recent_errors
            
        except Exception as e:
            self.logger.error(f"Error counting recent errors: {e}")
            return 0
    
    def _get_orchestration_stats(self) -> Dict[str, Any]:
        """Get orchestration statistics"""
        if not self.performance_history:
            return {"message": "No performance history available"}
        
        # Calculate basic stats
        recent_records = self.performance_history[-50:]  # Last 50 records
        
        agent_performance = {}
        for record in recent_records:
            agent = record['agent']
            if agent not in agent_performance:
                agent_performance[agent] = {"cycles": 0, "successes": 0}
            
            agent_performance[agent]["cycles"] += 1
            if record.get('performance', {}).get('successful', 0) > 0:
                agent_performance[agent]["successes"] += 1
        
        return {
            "total_cycles": len(self.performance_history),
            "recent_cycles": len(recent_records),
            "agent_performance": agent_performance,
            "system_uptime": self._calculate_system_uptime()
        }
    
    def _generate_system_recommendations(self, search_analytics: Dict, learning_recommendations: Dict, queue_status: Dict) -> List[str]:
        """Generate system-level recommendations"""
        recommendations = []
        
        # Analyze search performance
        if search_analytics.get('average_jobs_per_search', 0) < 5:
            recommendations.append("Consider broadening search criteria - low job discovery rate")
        
        # Analyze queue status
        if queue_status.get('total_in_queue', 0) > 20:
            recommendations.append("High number of queued applications - consider increasing processing frequency")
        
        # Analyze learning effectiveness
        model_confidence = learning_recommendations.get('performance_summary', {}).get('model_confidence', 0)
        if model_confidence < 0.6:
            recommendations.append("Low learning model confidence - more data needed for reliable predictions")
        
        return recommendations
    
    def _assess_system_health(self) -> str:
        """Assess overall system health"""
        # Check agent states
        failed_agents = sum(1 for state in self.agent_states.values() if state.get('status') == 'failed')
        
        if failed_agents > 1:
            return "unhealthy"
        elif failed_agents == 1:
            return "degraded"
        elif self.scheduler_running:
            return "healthy"
        else:
            return "manual"
    
    def _calculate_system_uptime(self) -> str:
        """Calculate system uptime"""
        start_time = self.agent_states.get("orchestration", {}).get("autonomous_started")
        if start_time:
            uptime = datetime.now() - datetime.fromisoformat(start_time)
            return str(uptime)
        return "N/A"
    
    def _auto_optimize_system(self, performance_report: Dict[str, Any]):
        """Automatically optimize system based on performance report"""
        # This could implement automatic optimization logic
        self.logger.info("Auto-optimization logic can be implemented here")
    
    def _save_performance_report(self, report: Dict[str, Any]):
        """Save performance report"""
        reports_dir = "data/performance_reports"
        os.makedirs(reports_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"{reports_dir}/performance_report_{timestamp}.json"
        
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving performance report: {e}")
    
    def _save_performance_history(self):
        """Save performance history"""
        try:
            with open("data/orchestration_performance.json", 'w') as f:
                json.dump(self.performance_history, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving performance history: {e}")
    
    def update_configuration(self, new_config: Dict[str, Any]):
        """Update orchestration configuration"""
        self.config.update(new_config)
        
        # If scheduling changed and autonomous mode is running, restart scheduler
        if self.scheduler_running and 'scheduling' in new_config:
            self.stop_autonomous_operation()
            time.sleep(2)
            self.start_autonomous_operation()
        
        # Save updated config
        try:
            with open("data/orchestration_config.json", 'w') as f:
                json.dump(self.config, f, indent=2)
            self.logger.info("Orchestration configuration updated")
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
    
    def __del__(self):
        """Cleanup on deletion"""
        if self.scheduler_running:
            self.stop_autonomous_operation()