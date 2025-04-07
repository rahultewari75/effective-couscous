To run app locally you need a .env file with an email that will send emails.

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=sender@email_domain.com
SMTP_PASS="my_app_password"

Then you need to modify the email of the default attorneys to put some attorneys in the database. That way the email will be sent from sender@email_domain.com and received by an attorney. 

To test the routes you can use /docs 

Run the server using:
`uvicorn server:app`
