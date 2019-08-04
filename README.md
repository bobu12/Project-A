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
   I did some investigation and found Amazon Aurora MySQL DB is compatible with MYSQL and flexibility to control autoscaling,low latency and is cost effective.However this solution needs to tested with the Magneto tool.
   In Auroa MYSQL DB we can use the below paramerts in the Cloud Format template to enable autoscaling after the DB usage crosses a particular threshold.
   
3. I nalysed the problem statement and realised CloudFront can be used to perform low latency for SEO purpose.However for the assignment , 
   I need to create a EC2 instance where I will be hosting the WebServer and establishing a connectivity with RDS instance.

Steps to migrate MYQSL DB to RDS -
1. This can be done using , AWS Database Migration Service or by using MySQL Workbench tool.For my demo I used the MYSQL dump and imported to the RDS MYSQL Db using MYSQL workbench. I have also gone through the steps mentioned in AWS DB migration service.
Question 2
----------
2. After releasing the new architecture, business takes on, and the client decides to add customer reviews.
Do you need to alter your architecture? And if so, how?

Comments -
TO add customer review , there need not be any change in the architecture , however this would require a additional Table in the Database instance.The cloumns of the TABLE_Comments will be [Cutomer_Name,Product_id,Comments]
When user will be entering comments on the product web page , it will be posted to the database table and will be retried from the database when the product page is opened by users.(I could not complete the web page design for this reqirement).

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

Amazon S3 provide read-after-write consistancy for PUTs to new objects (new key). 
Response (Get after overwrite PUT (PUT to an existing key)) changes the existing object so that a subsequent GET may fetch the previous and inconsistant object.
I configured the S3 Bucket policy and CORS Configaration to enable GET,POST and PUT methods.
I also designed a PHP page to upload the videos to S3 , however I am getting error while S3Client in the PHP page.
Refer to Bucket.php for code.
Solution 1 :We can set up logic in the PUT call to check the video consitancy of the video.
Solution 2: I researched and found the S3 comes with Python API distribution.
Hence I have designed a program which can be scheduled from the Web Server (CRON JOB),
This program navigates to the S3 instance , lists down the files uploaded and filters out the 
files which dnot contain .Mp4 and .3GP extension.Once the report is generated , the program can send a email to 
group highlighting the incorrect files uploaded.
