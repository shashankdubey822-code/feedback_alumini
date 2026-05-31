# Student Feedback Upload Mapping

This CSV maps cleanly into the dashboard schema used by the backend.

| Uploaded CSV column | Canonical backend field |
| --- | --- |
| `Timestamp` | `timestamp_display` |
| `Name of Student` | `name_of_student` |
| `Department` | `department` |
| `Roll No.` | `roll_no` |
| `Date of the Lecture` | `date_of_lecture` |
| `Alumni Speaker Name` | `alumni_speaker_name` |
| `Did the session help you gain a better understanding of industry trends or career paths?` | `session_help_understanding` |
| `What aspect of the session did you find most valuable?` | `aspect_most_valuable` |
| `How would you rate the session overall?` | `session_rating` |
| `What improvements or suggestions would you recommend for future alumni sessions?` | `improvements_suggestions` |
| `Any specific topics or areas you’d like future alumni speakers to cover?` | `future_topics` |

The current backend upload normalizer already recognizes these names and converts them into the dashboard fields.
