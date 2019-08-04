Question 1
----------
1. Design an architecture which incorporates the following client needs. The clients know that his whole setup is going
to evolve constantly. Include a cloud formation template for programmable infrastructure for your design.
Needs to be scalable and flexible
Needs to have low latency for SEO purposes
Needs to be cost effective

Comments - 
Preparing the initial set up for Demo -
The presentation contains the initial architecture draft of the problem. The cloud formation template is Initial_Template.json .
I have created a sample Website to demonstrate the demo . The website is coded in php and also contains a .sql file which needs to be uploaded to the MY SQL DB.
In the initial phase of the assignment , I had limited knowledge on hosting website . Hence I did some research and slected XAMPP V3.2.4 (which is a open source webserver solution) .The website contains login page and Product page (which allows user to enter product detail, upload thubnail , video and image).

Requirement Analysis 
1. The webshop is hosted on e-commerce tool Magneto. Did some research and found Magneto v2.1.2 is compartible with DB MySql V 5.7.X
2. The RDS set up in AWS needs to be scalable and flexible ( MultiAZ set up and configuring MasterDB and Replica DB).
   I did some investigation and found Amazon Auto DB is compatible with MYSQL and flexibility to control autoscaling,low latency and is cost effective.
   However this solution needs to tested with the Magneto tool.
3. I nalysed the problem statement and realised CloudFront can be used to perform low latency for SEO purpose.However for the assignment , 
   I need to create a EC2 instance where I will be hosting the WebServer and establishing a connectivity with RDS instance.

Question 2
----------
2. After releasing the new architecture, business takes on, and the client decides to add customer reviews.
Do you need to alter your architecture? And if so, how?

Question 3
----------
3. At some point, one of the customer employees is getting very good at creating vlogs, and the client wants to give
customers the opportunity to upload videos with their reviews. They want to store the thumbnails and videos for later
processing, and they want to show thumbnails of the videos underneath the product pages.
Alter your architecture to process and store these videos.

Question 4
----------
4. At some point, some clients uploaded non-compliant video's and which created a huge marketing issue. The client
now wants to screen the uploaded video's before putting them online, but with minimal costs.
Alter your architecture to be able to screen and process these video's.
