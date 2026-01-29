"""
Logging configuration for Mémoire des Territoires.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Try to import Rich, but make it optional
try:
    from rich.logging import RichHandler
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def setup_logger(
    name: str = "memoire_territoires",
    level: str = "INFO",
    log_file: Optional[str] = None,
    use_rich: bool = True
) -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        use_rich: Use Rich handler for beautiful console output
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler
    if use_rich:
        console_handler = RichHandler(
            rich_tracebacks=True,
            markup=True,
            show_time=True,
            show_level=True,
            show_path=True
        )
    else:
        console_handler = logging.StreamHandler(sys.stdout)
    
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    if not use_rich:
        console_handler.setFormatter(console_format)
    
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


class AgentLogger:
    """Specialized logger for agents with metrics tracking."""
    
    def __init__(self, agent_name: str, logger: Optional[logging.Logger] = None):
        """
        Initialize agent logger.
        
        Args:
            agent_name: Name of the agent
            logger: Base logger to use (creates new one if None)
        """
        self.agent_name = agent_name
        self.logger = logger or logging.getLogger(agent_name)
        self.start_time = None
        self.metrics = []
    
    def log_start(self, task: str, inputs: dict = None):
        """
        Log start of a task.
        
        Args:
            task: Task description
            inputs: Optional input data
        """
        self.start_time = datetime.now()
        self.logger.info(f"[{self.agent_name}] START: {task}")
        if inputs:
            self.logger.debug(f"[{self.agent_name}] Inputs: {inputs}")
    
    def log_end(self, task: str, outputs: dict = None, status: str = "success"):
        """
        Log end of a task with duration.
        
        Args:
            task: Task description
            outputs: Optional output data
            status: Task status (success, error, warning)
        """
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            self.logger.info(
                f"[{self.agent_name}] END: {task} ({duration:.2f}s) - {status.upper()}"
            )
            
            # Record metric
            self.metrics.append({
                'agent': self.agent_name,
                'task': task,
                'duration': duration,
                'status': status,
                'timestamp': datetime.now().isoformat()
            })
        else:
            self.logger.info(f"[{self.agent_name}] END: {task} - {status.upper()}")
        
        if status == "error" and outputs:
            self.logger.error(f"[{self.agent_name}] Error details: {outputs}")
        elif outputs:
            self.logger.debug(f"[{self.agent_name}] Outputs: {outputs}")
    
    def log_progress(self, message: str, progress: Optional[float] = None):
        """
        Log progress update.
        
        Args:
            message: Progress message
            progress: Optional progress percentage (0-100)
        """
        if progress is not None:
            self.logger.info(f"[{self.agent_name}] Progress: {message} ({progress:.1f}%)")
        else:
            self.logger.info(f"[{self.agent_name}] Progress: {message}")
    
    def log_warning(self, message: str):
        """Log warning."""
        self.logger.warning(f"[{self.agent_name}] WARNING: {message}")
    
    def log_error(self, message: str, exc_info: bool = False):
        """Log error."""
        self.logger.error(f"[{self.agent_name}] ERROR: {message}", exc_info=exc_info)
    
    def get_metrics(self) -> list:
        """Get recorded metrics."""
        return self.metrics
