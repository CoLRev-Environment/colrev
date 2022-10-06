import axios from "axios";

axios.interceptors.response.use(undefined, (error) => {
  console.log("An unexpected error occured", error);
  // alert(`An unexpected error occured.`);

  return Promise.reject(error); // return control to the catch blocks
});

const httpService = {
  get: axios.get,
  post: axios.post,
  put: axios.put,
  delete: axios.delete,
};

export default httpService;
