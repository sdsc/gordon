#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define MiB 1048576

int main(int argc, char *argv[]){

  /* Repeated allocate and populate 1MiB arrays */
  /* with random numbers. */
  /* Default size is 1GiB */
  /* Usage: $ grow-mem [GiB] */
  /* Where [GiB] is the integer number of GiB to allocate */

  int i, j, k, array_index;
  int n_gib = 1;

  if( argc == 2 ){
    n_gib = atoi(argv[1]);
  }

  int n_arrays = n_gib*1024;

  int **arrays = malloc(n_arrays*sizeof(int *));
  int array_size = MiB/sizeof(int);

  srand(time(NULL));

  clock_t start_time, end_time;
  float seconds;

  for(i = 0; i < n_gib; i++){
    /* Start timer */
    start_time = clock();

    for(j = 0; j < 1024; j++){
      array_index = i*1024 + j;
      /* allocate new 1MiB array of integers */

      arrays[array_index] = malloc(MiB);
      for(k = 0; k < array_size; k++){
        arrays[array_index][k] = rand();
      }
    }

    /* Print current time delta */
    end_time = clock();
    seconds = (float)(end_time - start_time) / CLOCKS_PER_SEC;

    printf("GiB %d took %f seconds\n", i + 1, seconds);
  }


  /* De-allocate array */
  start_time = clock();

  for(i = 0; i < n_gib; i++){
    for(j = 0; j < 1024; j++){
      array_index = i*1024 + j;
      free(arrays[array_index]);
    }
  }
  
  free(arrays);

  end_time = clock();
  seconds = (float)(end_time - start_time) / CLOCKS_PER_SEC;
  
  printf("# Freeing arrays took %f seconds\n", seconds);

  return 0;
}
