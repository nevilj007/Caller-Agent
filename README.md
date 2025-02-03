Steps to execute the program:



1.download and open docker



2.Run the following command in the bash terminal:
docker run -d \
  -e POSTGRES_DB=ai \
  -e POSTGRES_USER=ai \
  -e POSTGRES_PASSWORD=ai \
  -e PGDATA=/var/lib/postgresql/data/pgdata \
  -v pgvolume:/var/lib/postgresql/data \
  -p 5532:5432 \
  --name pgvector \
  phidata/pgvector:16


 
3.Open the terminal and go the directory inside you have cloned the project


4.run the code 
