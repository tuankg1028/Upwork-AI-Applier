import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
import calendar
import pytz
from icalendar import Calendar, Event, vDDDTypes
import tempfile
import os

from .logger import logger, TimedOperation
from .error_handler import with_retry, ErrorContext
from .config import get_config
from .database import get_database_manager

class EventType(Enum):
    """Types of calendar events"""
    APPLICATION_DEADLINE = "application_deadline"
    FOLLOW_UP_REMINDER = "follow_up_reminder"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    PROJECT_DEADLINE = "project_deadline"
    CLIENT_MEETING = "client_meeting"
    AVAILABILITY_BLOCK = "availability_block"
    SKILL_DEVELOPMENT = "skill_development"
    PORTFOLIO_UPDATE = "portfolio_update"

class EventPriority(Enum):
    """Priority levels for calendar events"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class EventStatus(Enum):
    """Status of calendar events"""
    SCHEDULED = "scheduled"
    REMINDED = "reminded"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    MISSED = "missed"

@dataclass
class CalendarEvent:
    """Represents a calendar event"""
    event_id: str
    event_type: EventType
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    priority: EventPriority
    status: EventStatus
    reminder_minutes: List[int]
    metadata: Dict[str, Any]
    job_id: Optional[str] = None
    client_info: Optional[str] = None
    location: Optional[str] = None
    attendees: List[str] = None
    created_at: datetime = None
    updated_at: datetime = None

@dataclass
class CalendarSchedule:
    """Represents a schedule of calendar events"""
    schedule_id: str
    events: List[CalendarEvent]
    start_date: datetime
    end_date: datetime
    total_events: int
    high_priority_events: int
    conflicts: List[str]
    recommendations: List[str]
    generated_at: datetime

class CalendarEventGenerator:
    """Generates calendar events based on job applications and follow-ups"""
    
    def __init__(self):
        self.config = get_config()
        self.db_manager = get_database_manager()
        
    async def generate_application_events(self, job_data: Dict[str, Any],
                                        application_data: Dict[str, Any],
                                        followup_strategy: Any) -> List[CalendarEvent]:
        """Generate calendar events for a job application"""
        
        events = []
        
        try:
            # 1. Application deadline reminder
            if self._has_deadline(job_data):
                deadline_event = await self._create_deadline_event(job_data, application_data)
                events.append(deadline_event)
            
            # 2. Follow-up reminders from strategy
            if followup_strategy and followup_strategy.timeline:
                followup_events = await self._create_followup_events(
                    job_data, followup_strategy
                )
                events.extend(followup_events)
            
            # 3. Interview preparation time block
            if self._should_block_interview_time(job_data, application_data):
                interview_prep_event = await self._create_interview_prep_event(
                    job_data, application_data
                )
                events.append(interview_prep_event)
            
            # 4. Availability update reminder
            availability_event = await self._create_availability_reminder(job_data)
            events.append(availability_event)
            
            logger.info(f"Generated {len(events)} calendar events for job {job_data.get('job_id', 'unknown')}")
            return events
            
        except Exception as e:
            logger.error(f"Error generating calendar events: {e}")
            return []
    
    def _has_deadline(self, job_data: Dict[str, Any]) -> bool:
        """Check if job has a deadline"""
        description = job_data.get('description', '').lower()
        return any(keyword in description for keyword in ['deadline', 'due', 'urgent', 'asap'])
    
    async def _create_deadline_event(self, job_data: Dict[str, Any],
                                   application_data: Dict[str, Any]) -> CalendarEvent:
        """Create a deadline reminder event"""
        
        # Estimate deadline based on job urgency
        deadline_days = self._estimate_deadline_days(job_data)
        start_time = datetime.now() + timedelta(days=deadline_days)
        
        event = CalendarEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.APPLICATION_DEADLINE,
            title=f"Application Deadline: {job_data.get('title', 'Unknown Job')[:50]}",
            description=f"Deadline reminder for job application.\n\nJob: {job_data.get('title', 'Unknown')}\nQuality Score: {application_data.get('quality_score', 'N/A')}\nClient: {job_data.get('client_location', 'Unknown')}",
            start_time=start_time,
            end_time=start_time + timedelta(minutes=30),
            priority=self._determine_deadline_priority(job_data),
            status=EventStatus.SCHEDULED,
            reminder_minutes=[60, 15],  # 1 hour and 15 minutes before
            metadata={
                'job_title': job_data.get('title', 'Unknown'),
                'estimated_deadline': True,
                'urgency_level': self._assess_urgency(job_data)
            },
            job_id=job_data.get('job_id'),
            created_at=datetime.now()
        )
        
        return event
    
    def _estimate_deadline_days(self, job_data: Dict[str, Any]) -> int:
        """Estimate deadline in days based on job description"""
        description = job_data.get('description', '').lower()
        
        if 'asap' in description or 'urgent' in description:
            return 1
        elif 'quick' in description or 'fast' in description:
            return 2
        elif 'week' in description:
            return 7
        elif 'month' in description:
            return 30
        else:
            return 3  # Default 3 days
    
    def _determine_deadline_priority(self, job_data: Dict[str, Any]) -> EventPriority:
        """Determine priority for deadline event"""
        description = job_data.get('description', '').lower()
        payment_rate = job_data.get('payment_rate', '')
        
        # High priority for urgent or high-paying jobs
        if 'urgent' in description or 'asap' in description:
            return EventPriority.URGENT
        
        if '$1000' in payment_rate or '$2000' in payment_rate:
            return EventPriority.HIGH
        
        if '$500' in payment_rate or '$100' in payment_rate:
            return EventPriority.MEDIUM
        
        return EventPriority.MEDIUM
    
    def _assess_urgency(self, job_data: Dict[str, Any]) -> str:
        """Assess urgency level of job"""
        description = job_data.get('description', '').lower()
        
        if 'asap' in description:
            return 'immediate'
        elif 'urgent' in description:
            return 'high'
        elif 'quick' in description:
            return 'medium'
        else:
            return 'normal'
    
    async def _create_followup_events(self, job_data: Dict[str, Any],
                                    followup_strategy: Any) -> List[CalendarEvent]:
        """Create follow-up reminder events"""
        
        events = []
        
        for action in followup_strategy.timeline:
            event = CalendarEvent(
                event_id=str(uuid.uuid4()),
                event_type=EventType.FOLLOW_UP_REMINDER,
                title=f"Follow-up: {action.followup_type.value.replace('_', ' ').title()}",
                description=f"Follow-up reminder for job application.\n\nJob: {job_data.get('title', 'Unknown')}\nAction: {action.followup_type.value}\nMessage: {action.message[:100]}...",
                start_time=action.scheduled_time,
                end_time=action.scheduled_time + timedelta(minutes=15),
                priority=self._action_priority_to_event_priority(action.priority),
                status=EventStatus.SCHEDULED,
                reminder_minutes=[30, 10],  # 30 minutes and 10 minutes before
                metadata={
                    'followup_action_id': action.action_id,
                    'followup_type': action.followup_type.value,
                    'client_success_rate': action.metadata.get('success_probability', 0)
                },
                job_id=job_data.get('job_id'),
                created_at=datetime.now()
            )
            
            events.append(event)
        
        return events
    
    def _action_priority_to_event_priority(self, action_priority: int) -> EventPriority:
        """Convert action priority to event priority"""
        if action_priority >= 8:
            return EventPriority.URGENT
        elif action_priority >= 6:
            return EventPriority.HIGH
        elif action_priority >= 4:
            return EventPriority.MEDIUM
        else:
            return EventPriority.LOW
    
    def _should_block_interview_time(self, job_data: Dict[str, Any],
                                   application_data: Dict[str, Any]) -> bool:
        """Check if we should block time for interview preparation"""
        quality_score = application_data.get('quality_score', 0)
        return quality_score > 80  # Only for high-quality applications
    
    async def _create_interview_prep_event(self, job_data: Dict[str, Any],
                                         application_data: Dict[str, Any]) -> CalendarEvent:
        """Create interview preparation time block"""
        
        # Schedule interview prep for 1 week after application
        start_time = datetime.now() + timedelta(days=7)
        
        event = CalendarEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.INTERVIEW_SCHEDULED,
            title=f"Interview Prep: {job_data.get('title', 'Unknown Job')[:50]}",
            description=f"Time blocked for interview preparation.\n\nJob: {job_data.get('title', 'Unknown')}\nQuality Score: {application_data.get('quality_score', 'N/A')}\nPrep Time: 1 hour",
            start_time=start_time,
            end_time=start_time + timedelta(hours=1),
            priority=EventPriority.HIGH,
            status=EventStatus.SCHEDULED,
            reminder_minutes=[60],  # 1 hour before
            metadata={
                'prep_type': 'interview_preparation',
                'quality_score': application_data.get('quality_score', 0)
            },
            job_id=job_data.get('job_id'),
            created_at=datetime.now()
        )
        
        return event
    
    async def _create_availability_reminder(self, job_data: Dict[str, Any]) -> CalendarEvent:
        """Create availability update reminder"""
        
        # Schedule availability update for 2 weeks after application
        start_time = datetime.now() + timedelta(days=14)
        
        event = CalendarEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.AVAILABILITY_BLOCK,
            title=f"Update Availability: {job_data.get('title', 'Unknown Job')[:50]}",
            description=f"Reminder to update availability status.\n\nJob: {job_data.get('title', 'Unknown')}\nAction: Check application status and update availability",
            start_time=start_time,
            end_time=start_time + timedelta(minutes=15),
            priority=EventPriority.LOW,
            status=EventStatus.SCHEDULED,
            reminder_minutes=[15],  # 15 minutes before
            metadata={
                'action_type': 'availability_update',
                'automation_generated': True
            },
            job_id=job_data.get('job_id'),
            created_at=datetime.now()
        )
        
        return event

class CalendarScheduler:
    """Manages calendar schedules and conflicts"""
    
    def __init__(self):
        self.config = get_config()
        self.event_generator = CalendarEventGenerator()
        
    async def create_schedule(self, applications: List[Dict[str, Any]],
                            followup_strategies: List[Any],
                            start_date: datetime,
                            end_date: datetime) -> CalendarSchedule:
        """Create a comprehensive calendar schedule"""
        
        with TimedOperation("calendar_schedule_creation"):
            all_events = []
            
            # Generate events for each application
            for i, app_data in enumerate(applications):
                followup_strategy = followup_strategies[i] if i < len(followup_strategies) else None
                
                job_data = {
                    'job_id': app_data.get('job_id', str(uuid.uuid4())),
                    'title': app_data.get('job_title', 'Unknown'),
                    'description': app_data.get('job_description', ''),
                    'payment_rate': app_data.get('payment_rate', ''),
                    'client_location': app_data.get('client_location', 'Unknown')
                }
                
                application_data = {
                    'quality_score': app_data.get('quality_score', 70),
                    'quality_level': app_data.get('quality_level', 'good')
                }
                
                events = await self.event_generator.generate_application_events(
                    job_data, application_data, followup_strategy
                )
                
                all_events.extend(events)
            
            # Filter events within date range
            filtered_events = [
                event for event in all_events
                if start_date <= event.start_time <= end_date
            ]
            
            # Sort events by start time
            filtered_events.sort(key=lambda x: x.start_time)
            
            # Detect conflicts
            conflicts = self._detect_conflicts(filtered_events)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(filtered_events, conflicts)
            
            # Count high priority events
            high_priority_count = sum(
                1 for event in filtered_events 
                if event.priority in [EventPriority.HIGH, EventPriority.URGENT]
            )
            
            schedule = CalendarSchedule(
                schedule_id=str(uuid.uuid4()),
                events=filtered_events,
                start_date=start_date,
                end_date=end_date,
                total_events=len(filtered_events),
                high_priority_events=high_priority_count,
                conflicts=conflicts,
                recommendations=recommendations,
                generated_at=datetime.now()
            )
            
            logger.info(f"Created calendar schedule: {len(filtered_events)} events, {len(conflicts)} conflicts")
            return schedule
    
    def _detect_conflicts(self, events: List[CalendarEvent]) -> List[str]:
        """Detect time conflicts between events"""
        conflicts = []
        
        for i, event1 in enumerate(events):
            for j, event2 in enumerate(events[i+1:], i+1):
                if self._events_overlap(event1, event2):
                    conflicts.append(
                        f"Conflict: {event1.title} overlaps with {event2.title} "
                        f"at {event1.start_time.strftime('%Y-%m-%d %H:%M')}"
                    )
        
        return conflicts
    
    def _events_overlap(self, event1: CalendarEvent, event2: CalendarEvent) -> bool:
        """Check if two events overlap in time"""
        return (event1.start_time < event2.end_time and 
                event2.start_time < event1.end_time)
    
    def _generate_recommendations(self, events: List[CalendarEvent],
                                conflicts: List[str]) -> List[str]:
        """Generate scheduling recommendations"""
        recommendations = []
        
        # Check for overloaded days
        daily_counts = {}
        for event in events:
            date_key = event.start_time.date()
            daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
        
        overloaded_days = [date for date, count in daily_counts.items() if count > 5]
        if overloaded_days:
            recommendations.append(f"Consider redistributing events on {len(overloaded_days)} overloaded days")
        
        # Check for conflicts
        if conflicts:
            recommendations.append(f"Resolve {len(conflicts)} scheduling conflicts")
        
        # Check for clustering
        urgent_events = [e for e in events if e.priority == EventPriority.URGENT]
        if len(urgent_events) > 3:
            recommendations.append("Consider spacing out urgent events for better focus")
        
        # Check for follow-up spacing
        followup_events = [e for e in events if e.event_type == EventType.FOLLOW_UP_REMINDER]
        if len(followup_events) > 10:
            recommendations.append("High volume of follow-ups - consider batching similar actions")
        
        return recommendations

class CalendarExporter:
    """Exports calendar events to various formats"""
    
    def __init__(self):
        self.config = get_config()
        
    async def export_to_ical(self, schedule: CalendarSchedule,
                           filename: Optional[str] = None) -> str:
        """Export schedule to iCal format"""
        
        try:
            # Create calendar
            cal = Calendar()
            cal.add('prodid', '-//Upwork AI Applier//Calendar//EN')
            cal.add('version', '2.0')
            cal.add('calscale', 'GREGORIAN')
            cal.add('method', 'PUBLISH')
            
            # Add events
            for event in schedule.events:
                cal_event = Event()
                cal_event.add('uid', event.event_id)
                cal_event.add('summary', event.title)
                cal_event.add('description', event.description)
                cal_event.add('dtstart', event.start_time)
                cal_event.add('dtend', event.end_time)
                cal_event.add('priority', self._priority_to_ical_priority(event.priority))
                cal_event.add('status', event.status.value.upper())
                
                # Add reminders
                for minutes in event.reminder_minutes:
                    alarm = cal_event.add('valarm')
                    alarm.add('action', 'DISPLAY')
                    alarm.add('description', f"Reminder: {event.title}")
                    alarm.add('trigger', timedelta(minutes=-minutes))
                
                # Add location if available
                if event.location:
                    cal_event.add('location', event.location)
                
                # Add attendees if available
                if event.attendees:
                    for attendee in event.attendees:
                        cal_event.add('attendee', f'mailto:{attendee}')
                
                cal.add_component(cal_event)
            
            # Generate filename if not provided
            if not filename:
                filename = f"upwork_schedule_{schedule.schedule_id[:8]}.ics"
            
            # Write to file
            with open(filename, 'wb') as f:
                f.write(cal.to_ical())
            
            logger.info(f"Exported calendar to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error exporting to iCal: {e}")
            return ""
    
    def _priority_to_ical_priority(self, priority: EventPriority) -> int:
        """Convert event priority to iCal priority"""
        priority_map = {
            EventPriority.LOW: 9,
            EventPriority.MEDIUM: 5,
            EventPriority.HIGH: 3,
            EventPriority.URGENT: 1
        }
        return priority_map.get(priority, 5)
    
    async def export_to_json(self, schedule: CalendarSchedule,
                           filename: Optional[str] = None) -> str:
        """Export schedule to JSON format"""
        
        try:
            # Convert to JSON-serializable format
            schedule_dict = {
                'schedule_id': schedule.schedule_id,
                'start_date': schedule.start_date.isoformat(),
                'end_date': schedule.end_date.isoformat(),
                'total_events': schedule.total_events,
                'high_priority_events': schedule.high_priority_events,
                'conflicts': schedule.conflicts,
                'recommendations': schedule.recommendations,
                'generated_at': schedule.generated_at.isoformat(),
                'events': []
            }
            
            for event in schedule.events:
                event_dict = {
                    'event_id': event.event_id,
                    'event_type': event.event_type.value,
                    'title': event.title,
                    'description': event.description,
                    'start_time': event.start_time.isoformat(),
                    'end_time': event.end_time.isoformat(),
                    'priority': event.priority.value,
                    'status': event.status.value,
                    'reminder_minutes': event.reminder_minutes,
                    'metadata': event.metadata,
                    'job_id': event.job_id,
                    'client_info': event.client_info,
                    'location': event.location,
                    'attendees': event.attendees
                }
                schedule_dict['events'].append(event_dict)
            
            # Generate filename if not provided
            if not filename:
                filename = f"upwork_schedule_{schedule.schedule_id[:8]}.json"
            
            # Write to file
            with open(filename, 'w') as f:
                json.dump(schedule_dict, f, indent=2)
            
            logger.info(f"Exported calendar to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return ""

class CalendarIntegration:
    """Main calendar integration system"""
    
    def __init__(self):
        self.config = get_config()
        self.scheduler = CalendarScheduler()
        self.exporter = CalendarExporter()
        
    async def create_application_calendar(self, applications: List[Dict[str, Any]],
                                        followup_strategies: List[Any],
                                        days_ahead: int = 30) -> CalendarSchedule:
        """Create calendar for job applications"""
        
        start_date = datetime.now()
        end_date = start_date + timedelta(days=days_ahead)
        
        schedule = await self.scheduler.create_schedule(
            applications, followup_strategies, start_date, end_date
        )
        
        return schedule
    
    async def export_calendar(self, schedule: CalendarSchedule,
                            format: str = 'ical',
                            filename: Optional[str] = None) -> str:
        """Export calendar to specified format"""
        
        if format.lower() == 'ical':
            return await self.exporter.export_to_ical(schedule, filename)
        elif format.lower() == 'json':
            return await self.exporter.export_to_json(schedule, filename)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    async def get_upcoming_events(self, schedule: CalendarSchedule,
                                days_ahead: int = 7) -> List[CalendarEvent]:
        """Get upcoming events for the next N days"""
        
        cutoff_date = datetime.now() + timedelta(days=days_ahead)
        
        upcoming = [
            event for event in schedule.events
            if datetime.now() <= event.start_time <= cutoff_date
            and event.status == EventStatus.SCHEDULED
        ]
        
        return sorted(upcoming, key=lambda x: x.start_time)
    
    async def get_daily_summary(self, schedule: CalendarSchedule,
                              target_date: datetime) -> Dict[str, Any]:
        """Get daily summary of events"""
        
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        daily_events = [
            event for event in schedule.events
            if start_of_day <= event.start_time < end_of_day
        ]
        
        summary = {
            'date': target_date.strftime('%Y-%m-%d'),
            'total_events': len(daily_events),
            'high_priority_events': len([e for e in daily_events if e.priority in [EventPriority.HIGH, EventPriority.URGENT]]),
            'event_types': {},
            'events': daily_events
        }
        
        # Count by event type
        for event in daily_events:
            event_type = event.event_type.value
            summary['event_types'][event_type] = summary['event_types'].get(event_type, 0) + 1
        
        return summary

# Global calendar integration instance
calendar_integration = CalendarIntegration()

# Convenience functions
async def create_application_calendar(applications: List[Dict[str, Any]],
                                    followup_strategies: List[Any],
                                    days_ahead: int = 30) -> CalendarSchedule:
    """Create calendar for job applications"""
    return await calendar_integration.create_application_calendar(
        applications, followup_strategies, days_ahead
    )

async def export_calendar_to_ical(schedule: CalendarSchedule,
                                filename: Optional[str] = None) -> str:
    """Export calendar to iCal format"""
    return await calendar_integration.export_calendar(schedule, 'ical', filename)

async def get_upcoming_events(schedule: CalendarSchedule,
                            days_ahead: int = 7) -> List[CalendarEvent]:
    """Get upcoming events"""
    return await calendar_integration.get_upcoming_events(schedule, days_ahead)